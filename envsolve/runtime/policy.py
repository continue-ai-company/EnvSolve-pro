from __future__ import annotations

from dataclasses import dataclass, field
from textwrap import dedent
from typing import Any
import hashlib
import json

from envsolve.constraints.frontier import build_causal_constraint_frontier
from envsolve.operations.planner import ConstraintOperationPlanner
from envsolve.constraints.models import (
    ConstraintDomain,
    ConstraintPredicate,
    ConstraintRole,
)
from envsolve.operations import (
    parse_operation_feasibility_subject,
    verified_failed_operation_prefix,
)
from envsolve.solver import (
    DeploymentCandidate,
    EpisodeProviderAcquisitionFailed,
    RecoverablePolicyError,
)
from envsolve.state import EnvironmentState


BASE_SYSTEM_PROMPT = dedent(
    """
    You are the candidate generator inside EnvSolve. Produce one complete,
    cumulative, replayable shell program that configures the current Python
    repository from a clean checkout. You do not have a shell tool. Use only
    the repository profile and prior fresh-container feedback below.

    The program may install Python packages, system packages, configure a
    Python runtime, activate a project virtual environment, or export safe
    environment variables. It must not inspect files, run tests, edit project
    source, create fake modules, suppress diagnostics, or use benchmark
    evaluator output. Every new candidate must include all still-needed setup,
    not merely a delta from the previous candidate.

    An import module name is not necessarily a package distribution name. Do
    not install a distribution solely because its spelling matches a missing
    module; use repository evidence, runtime facts, and prior execution errors.
    Treat only active module requirements as repair obligations. An unresolved
    module marked inactive is an observation, not an install target.

    Return exactly one JSON object with string fields "script" and
    "rationale". Do not use Markdown fences or add other keys.
    """
).strip()

OPERATION_SYSTEM_PROMPT = dedent(
    """
    The state contains a machine-derived operation_plan. For every listed
    requirement, include at least one mutation whose kind is in
    allowed_operation_kinds. Preserve operations that support previously satisfied
    requirements because every candidate runs in a fresh environment. Use prior
    failures to change the program before a command that already failed. Entries in
    infeasible_operations apply only to the exact command in its recorded provider
    prefix context. A different command or a changed runtime/provider prefix remains
    allowed. The plan constrains the kind of repair; it does not authorize inventing
    package-to-module mappings.
    """
).strip()

CAUSAL_FRONTIER_SYSTEM_PROMPT = dedent(
    """
    The state contains a derived constraint_frontier. It preserves raw evidence
    but prioritizes executable root causes. A runtime_missing_dependency root
    groups surface imports by the actual missing_name that caused them to fail;
    surface counts measure amplification and are not independent package names.
    Repair or avoid a grounded root before enumerating its surface symptoms.
    Runtime compatibility roots and observed platform facts are evidence, not a
    closed action list. You may use any valid complete deployment program, and
    should consult the raw candidate and verifier feedback when the frontier is
    incomplete or ambiguous.
    """
).strip()

OPERATION_PROFILES = {"constraint-driven", "free-form"}
CONSTRAINT_PROFILES = {"flat", "causal-frontier"}


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}
        ]
        return "".join(parts)
    raise ValueError("Model response does not contain textual content")


@dataclass
class StructuredModelDeploymentPolicy:
    model: Any
    repository_profile: dict[str, Any]
    max_feedback_chars: int = 64_000
    candidate_language: str = ""
    operation_profile: str = "constraint-driven"
    constraint_profile: str = "flat"
    operation_planner: ConstraintOperationPlanner = field(
        default_factory=ConstraintOperationPlanner
    )

    def __post_init__(self) -> None:
        if not isinstance(self.repository_profile, dict):
            raise ValueError("Repository profile must be an object")
        if self.max_feedback_chars < 4_096:
            raise ValueError("Model feedback budget must be at least 4096 characters")
        if self.operation_profile not in OPERATION_PROFILES:
            raise ValueError(
                "Operation profile must be constraint-driven or free-form"
            )
        if self.constraint_profile not in CONSTRAINT_PROFILES:
            raise ValueError("Constraint profile must be flat or causal-frontier")
        self._next_candidate = 1

    @staticmethod
    def _json_size(value: Any) -> int:
        return len(json.dumps(value, ensure_ascii=True, sort_keys=True))

    @classmethod
    def _bounded_json_value(cls, value: Any, limit: int) -> Any:
        encoded = json.dumps(value, ensure_ascii=True, sort_keys=True)
        if len(encoded) <= limit:
            return value
        summary = {
            "truncated": True,
            "original_chars": len(encoded),
            "sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            "excerpt": "",
        }
        if cls._json_size(summary) > limit:
            return {"truncated": True}
        low = 0
        high = len(encoded)
        while low < high:
            middle = (low + high + 1) // 2
            summary["excerpt"] = cls._bounded_value(encoded, middle)
            if cls._json_size(summary) <= limit:
                low = middle
            else:
                high = middle - 1
        summary["excerpt"] = cls._bounded_value(encoded, low)
        return summary

    def _field_limit(self, weight: float) -> int:
        return max(128, int((self.max_feedback_chars - 2_048) * weight))

    def _constraint_view(
        self,
        state: EnvironmentState,
        *,
        compact_module_surfaces: bool = False,
    ) -> dict[str, Any]:
        report = self.operation_planner.constraint_engine.solve_state(state)
        groups: dict[str, list[dict[str, str]]] = {}
        module_surface_conflicts = 0
        for conflict in report.conflicts:
            if compact_module_surfaces and conflict.domain == "module":
                module_surface_conflicts += 1
                continue
            groups.setdefault(conflict.domain, []).append(
                {
                    "subject": conflict.subject,
                    "message": conflict.message,
                }
            )
        return {
            "conflict_count": len(report.conflicts),
            "groups": [
                {
                    "domain": domain,
                    "conflicts": sorted(
                        conflicts,
                        key=lambda item: (item["subject"], item["message"]),
                    ),
                }
                for domain, conflicts in sorted(groups.items())
            ],
            "module_surface_conflict_count": module_surface_conflicts,
            "provisional_constraint_count": len(report.provisional_constraints),
        }

    def _operation_prompt_view(self, state: EnvironmentState) -> dict[str, Any]:
        plan = self.operation_planner.plan(state)
        groups: dict[tuple[str, str, tuple[str, ...]], list[str]] = {}
        for requirement in plan.requirements:
            kinds = tuple(item.value for item in requirement.allowed_operation_kinds)
            groups.setdefault(
                (requirement.trigger.value, requirement.domain, kinds), []
            ).append(
                requirement.subject
            )
        return {
            "plan_id": plan.plan_id,
            "requirement_count": len(plan.requirements),
            "groups": [
                {
                    "trigger": trigger,
                    "domain": domain,
                    "allowed_operation_kinds": list(kinds),
                    "subjects": sorted(set(subjects)),
                }
                for (trigger, domain, kinds), subjects in sorted(groups.items())
            ],
            "unsupported_conflict_count": len(plan.unsupported_conflict_ids),
            "infeasible_operations": self._infeasible_operation_view(state),
        }

    def _infeasible_operation_view(
        self,
        state: EnvironmentState,
    ) -> list[dict[str, Any]]:
        failures: list[dict[str, Any]] = []
        for constraint in self.operation_planner.constraint_engine.typed_constraints(
            state
        ):
            if (
                constraint.domain is not ConstraintDomain.OPERATION
                or constraint.role is not ConstraintRole.FACT
                or constraint.predicate is not ConstraintPredicate.FEASIBLE
                or constraint.value is not False
                or constraint.confidence
                < self.operation_planner.constraint_engine.hard_confidence
            ):
                continue
            try:
                parsed = parse_operation_feasibility_subject(constraint.subject)
            except ValueError:
                continue
            source_candidate_id = constraint.scope_id
            if source_candidate_id is None:
                continue
            prefix = verified_failed_operation_prefix(
                state.verifications,
                source_candidate_id,
                parsed["command"],
            )
            if prefix is None:
                continue
            failures.append(
                {
                    "command": parsed["command"],
                    "constraint_id": constraint.constraint_id,
                    "failed_prefix_commands": list(prefix[:-1]),
                    "failure_class": parsed["failure_class"],
                    "retry_scope": (
                        "exact_command_and_relevant_provider_context"
                    ),
                    "source_candidate_id": source_candidate_id,
                }
            )
        return sorted(
            failures,
            key=lambda item: (
                item["failure_class"],
                item["command"],
                item["constraint_id"],
            ),
        )

    @classmethod
    def _candidate_view(cls, item: dict[str, Any]) -> dict[str, Any]:
        observation = item.get("observation")
        if not isinstance(observation, dict):
            observation = {}
        return {
            "candidate_id": item.get("action_id"),
            "script": cls._bounded_value(item.get("command"), 6_000),
            "status": item.get("status"),
            "exit_code": item.get("exit_code"),
            "observation": {
                "duration_seconds": observation.get("duration_seconds"),
                "stdout": cls._bounded_value(observation.get("stdout"), 2_000),
                "stderr": cls._bounded_value(observation.get("stderr"), 3_500),
            },
        }

    @classmethod
    def _verification_view(cls, item: dict[str, Any]) -> dict[str, Any]:
        details = item.get("details")
        if not isinstance(details, dict):
            details = {}
        diagnostic = details.get("verifier_details", details)
        return {
            "verification_id": item.get("verification_id"),
            "passed": item.get("passed"),
            "verifier": item.get("verifier"),
            "candidate_id": details.get("candidate_id"),
            "feedback_channel": details.get("feedback_channel"),
            "check_profile": details.get("check_profile"),
            "reported_passed": details.get("reported_passed"),
            "bootstrap_exit_code": details.get("bootstrap_exit_code"),
            "summary": details.get("summary"),
            "counterexample_count": details.get("counterexample_count"),
            "diagnostic": cls._bounded_json_value(diagnostic, 4_000),
        }

    def _state_projection(self, state: EnvironmentState) -> dict[str, Any]:
        causal = self.constraint_profile == "causal-frontier"
        weights = {
            "case": 0.03,
            "repository": 0.17,
            "candidates": 0.22,
            "conflicts": 0.08 if causal else 0.20,
            "module_requirements": 0.04,
            "frontier": 0.16,
            "policy_failures": 0.04,
            "verification": 0.10,
            "hypotheses": 0.08,
            "operation": 0.12,
        }
        actions = sorted(
            state.actions.values(),
            key=lambda item: int(item.get("state_metadata", {}).get("event_sequence", 0)),
        )[-2:]
        violated_constraints = tuple(
            item
            for item in state.constraints.values()
            if item.get("status") == "violated"
        )
        active_module_requirements: list[str] = []
        for item in violated_constraints:
            try:
                expression = json.loads(str(item.get("expression", "")))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if (
                expression.get("domain") == "module"
                and expression.get("role") == "requirement"
                and expression.get("predicate") == "present"
                and expression.get("value") is True
                and isinstance(expression.get("subject"), str)
            ):
                active_module_requirements.append(expression["subject"])
        recent_policy_failures = sorted(
            (
                item
                for item in state.failures.values()
                if str(item.get("category", "")).startswith("candidate-policy-")
            ),
            key=lambda item: int(item.get("state_metadata", {}).get("event_sequence", 0)),
        )[-2:]
        projection = {
            "case": self._bounded_json_value(
                state.case, self._field_limit(weights["case"])
            ),
            "repository_profile": self._bounded_json_value(
                self.repository_profile,
                self._field_limit(weights["repository"]),
            ),
            "prior_candidates": self._bounded_json_value(
                [self._candidate_view(item) for item in actions],
                self._field_limit(weights["candidates"]),
            ),
            "constraint_conflicts": self._bounded_json_value(
                self._constraint_view(
                    state,
                    compact_module_surfaces=causal,
                ),
                self._field_limit(weights["conflicts"]),
            ),
            "recent_policy_failures": self._bounded_json_value(
                [
                    {
                        "category": item.get("category"),
                        "message": item.get("message"),
                        "details": self._bounded_json_value(
                            item.get("details"), 1_000
                        ),
                    }
                    for item in recent_policy_failures
                ],
                self._field_limit(weights["policy_failures"]),
            ),
            "verification_feedback": self._bounded_json_value(
                [self._verification_view(item) for item in state.verifications[-2:]],
                self._field_limit(weights["verification"]),
            ),
            "active_hypotheses": self._bounded_json_value(
                [
                    {
                        "hypothesis_id": item.get("hypothesis_id"),
                        "statement": item.get("statement"),
                        "confidence": item.get("confidence"),
                        "evidence": [
                            self._bounded_json_value(
                                state.evidence[evidence_id].get("value"), 1_000
                            )
                            for evidence_id in item.get("evidence_ids", [])
                            if evidence_id in state.evidence
                        ],
                    }
                    for item in state.hypotheses.values()
                    if item.get("status") == "active"
                ],
                self._field_limit(weights["hypotheses"]),
            ),
        }
        if causal:
            projection["constraint_frontier"] = self._bounded_json_value(
                build_causal_constraint_frontier(
                    state,
                    self.operation_planner.constraint_engine,
                ),
                self._field_limit(weights["frontier"]),
            )
        else:
            projection["active_module_requirements"] = self._bounded_json_value(
                sorted(set(active_module_requirements)),
                self._field_limit(weights["module_requirements"]),
            )
        if self.operation_profile == "constraint-driven":
            projection["operation_plan"] = self._bounded_json_value(
                self._operation_prompt_view(state),
                self._field_limit(weights["operation"]),
            )
        encoded = json.dumps(projection, ensure_ascii=True, sort_keys=True)
        if len(encoded) > self.max_feedback_chars:
            raise ValueError("Bounded solver feedback exceeds the model context contract")
        return projection

    @classmethod
    def _bounded_value(cls, value: Any, limit: int) -> Any:
        if isinstance(value, str):
            if len(value) <= limit:
                return value
            marker = "...[truncated]..."
            if limit <= len(marker):
                return value[-limit:]
            head = (limit - len(marker)) // 2
            tail = limit - len(marker) - head
            return value[:head] + marker + value[-tail:]
        if isinstance(value, dict):
            return {
                str(key): cls._bounded_value(item, limit)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._bounded_value(item, limit) for item in value]
        return value

    def propose(self, state: EnvironmentState) -> DeploymentCandidate:
        projection = self._state_projection(state)
        system_prompt = BASE_SYSTEM_PROMPT
        if self.constraint_profile == "causal-frontier":
            system_prompt += "\n\n" + CAUSAL_FRONTIER_SYSTEM_PROMPT
        if self.operation_profile == "constraint-driven":
            system_prompt += "\n\n" + OPERATION_SYSTEM_PROMPT
        if self.candidate_language.strip():
            system_prompt += "\n\nCandidate language contract:\n" + self.candidate_language.strip()
        try:
            response = self.model.invoke(
                [
                    ("system", system_prompt),
                    (
                        "user",
                        "Produce the next complete candidate from this JSON state:\n"
                        + json.dumps(projection, ensure_ascii=True, sort_keys=True),
                    ),
                ]
            )
        except Exception as exc:
            details = self._length_finish_details(exc)
            if details is not None:
                raise RecoverablePolicyError(
                    "Model candidate reached the output token limit before parsing",
                    details=details,
                ) from exc
            if isinstance(exc, json.JSONDecodeError):
                attempts = int(getattr(exc, "provider_attempts", 1))
                raise EpisodeProviderAcquisitionFailed(attempts) from exc
            raise
        text = _response_text(response).strip()
        if not text:
            raise RecoverablePolicyError(
                "Model candidate has no final content",
                details=self._invalid_response_details(text, response),
            )
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RecoverablePolicyError(
                "Model candidate is not exact JSON",
                details=self._invalid_response_details(text, response),
            ) from exc
        if not isinstance(value, dict) or set(value) != {"script", "rationale"}:
            raise RecoverablePolicyError(
                "Model candidate must contain only script and rationale",
                details=self._invalid_response_details(text, response),
            )
        script = value.get("script")
        rationale = value.get("rationale")
        if not isinstance(script, str) or not isinstance(rationale, str):
            raise RecoverablePolicyError(
                "Model candidate fields must be strings",
                details=self._invalid_response_details(text, response),
            )
        metadata: dict[str, Any] = {
            "generator": "structured-model-policy-v1",
            "operation_profile": self.operation_profile,
            "constraint_profile": self.constraint_profile,
        }
        if self.constraint_profile == "causal-frontier":
            frontier_snapshot = projection["constraint_frontier"]
            encoded_frontier = json.dumps(
                frontier_snapshot,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            metadata["constraint_frontier_snapshot"] = frontier_snapshot
            metadata["constraint_frontier_sha256"] = hashlib.sha256(
                encoded_frontier.encode("utf-8")
            ).hexdigest()
        candidate = DeploymentCandidate(
            candidate_id=f"candidate-{self._next_candidate:04d}",
            script=script,
            rationale=rationale,
            metadata=metadata,
        )
        self._next_candidate += 1
        return candidate

    @classmethod
    def _invalid_response_details(
        cls, text: str, response: Any | None = None
    ) -> dict[str, Any]:
        metadata = getattr(response, "response_metadata", None)
        metadata = metadata if isinstance(metadata, dict) else {}
        usage = getattr(response, "usage_metadata", None)
        usage = usage if isinstance(usage, dict) else {}
        output_details = usage.get("output_token_details")
        output_details = output_details if isinstance(output_details, dict) else {}
        additional = getattr(response, "additional_kwargs", None)
        additional = additional if isinstance(additional, dict) else {}
        reasoning = additional.get("reasoning") or additional.get("reasoning_content")
        return {
            "response_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "response_excerpt": cls._bounded_value(text, 2_000),
            "final_content_empty": not bool(text),
            "finish_reason": metadata.get("finish_reason"),
            "output_tokens": usage.get("output_tokens"),
            "reasoning_tokens": output_details.get("reasoning"),
            "reasoning_content_present": bool(reasoning),
        }

    @classmethod
    def _length_finish_details(cls, error: BaseException) -> dict[str, Any] | None:
        if type(error).__name__ != "LengthFinishReasonError":
            return None
        completion = getattr(error, "completion", None)
        choices = _field(completion, "choices", ()) or ()
        choice = choices[0] if choices else None
        finish_reason = _field(choice, "finish_reason")
        if finish_reason not in {None, "length"}:
            return None
        message = _field(choice, "message")
        text = _field(message, "content", "") or ""
        usage = _field(completion, "usage")
        output_details = _field(usage, "completion_tokens_details")
        reasoning_tokens = _field(
            output_details,
            "reasoning_tokens",
            _field(output_details, "reasoning"),
        )
        return {
            "response_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "response_excerpt": cls._bounded_value(text, 2_000),
            "final_content_empty": not bool(text),
            "finish_reason": finish_reason or "length",
            "output_tokens": _field(
                usage,
                "completion_tokens",
                _field(usage, "output_tokens"),
            ),
            "reasoning_tokens": reasoning_tokens,
            "reasoning_content_present": bool(
                _field(message, "reasoning")
                or _field(message, "reasoning_content")
            ),
        }
