from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from typing import Any

from envsolve.runtime.operation_contract import (
    OPERATION_RELEVANCE_CONTEXT_SCHEMA,
    OPERATION_RELEVANCE_CONTRACT_SCHEMA,
    OperationRelevanceContract,
)
from envsolve.runtime.policy import StructuredModelDeploymentPolicy
from envsolve.solver import DeploymentCandidate, RecoverablePolicyError
from envsolve.state import EnvironmentState


EVIDENCE_DIRECTED_OPERATION_PROFILE = "evidence-directed"
_FREE_FORM_OUTPUT_INSTRUCTION = (
    'Return exactly one JSON object with string fields "script" and\n'
    '"rationale". Do not use Markdown fences or add other keys.'
)
_OPERATION_RELEVANCE_OUTPUT_INSTRUCTION = f"""
The state contains an operation_context. Keep the operation space open:
"script" is still one complete cumulative Bash program. Also provide an
operation_contract with schema "{OPERATION_RELEVANCE_CONTRACT_SCHEMA}".
Its target_finding_ids must name active_targets,
expected_resolved_finding_ids must be a non-empty subset of those targets,
and precondition_evidence_ids must cite available_precondition_evidence.
After the first goal observation, cite concrete execution, repository, or
retained-candidate evidence rather than only the broad goal or repository
profile.

operation_family has open string fields "tool", "mechanism", and "target".
It identifies the newly introduced causal repair, not cumulative setup
preserved from an earlier candidate. A same-family retry is valid only when
newly observed evidence changes its basis. The harness compares the predicted
finding delta with the next complete executable-goal snapshot.

Return exactly one JSON object with only "script", "rationale", and
"operation_contract". "script" and "rationale" are strings.
"operation_contract" has exactly:
{{
  "schema": "{OPERATION_RELEVANCE_CONTRACT_SCHEMA}",
  "target_finding_ids": ["..."],
  "precondition_evidence_ids": ["..."],
  "expected_resolved_finding_ids": ["..."],
  "operation_family": {{
    "tool": "...",
    "mechanism": "...",
    "target": "..."
  }}
}}
Do not use Markdown fences or add other keys.
""".strip()


def _response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict)
            and item.get("type") in {"text", "output_text"}
        )
    raise ValueError("Model response does not contain textual content")


class _ProjectedResponse:
    def __init__(self, original: Any, content: str) -> None:
        self._original = original
        self.content = content

    def __getattr__(self, name: str) -> Any:
        return getattr(self._original, name)


class _EvidenceDirectedModelProxy:
    def __init__(
        self,
        policy: EvidenceDirectedDeploymentPolicy,
        model: Any,
        state: EnvironmentState,
    ) -> None:
        self.policy = policy
        self.model = model
        self.state = state
        self.contract: OperationRelevanceContract | None = None

    def invoke(self, messages: Any) -> Any:
        prepared = list(messages)
        if not prepared or not isinstance(prepared[0], tuple):
            raise ValueError("Model prompt has an unsupported message shape")
        role, system_prompt = prepared[0]
        if not isinstance(system_prompt, str) or (
            _FREE_FORM_OUTPUT_INSTRUCTION not in system_prompt
        ):
            raise ValueError("Frozen free-form output instruction is unavailable")
        prepared[0] = (
            role,
            system_prompt.replace(
                _FREE_FORM_OUTPUT_INSTRUCTION,
                _OPERATION_RELEVANCE_OUTPUT_INSTRUCTION,
            ),
        )
        response = self.model.invoke(prepared)
        text = _response_text(response).strip()
        if not text:
            return response
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return response
        if not isinstance(value, dict) or set(value) != {
            "script",
            "rationale",
            "operation_contract",
        }:
            raise RecoverablePolicyError(
                "Evidence-directed candidate requires only script, rationale, "
                "and operation_contract",
                category="candidate-policy-operation-contract",
                details=self.policy._invalid_response_details(text, response),
            )
        script = value.get("script")
        rationale = value.get("rationale")
        if not isinstance(script, str) or not isinstance(rationale, str):
            raise RecoverablePolicyError(
                "Evidence-directed script and rationale must be strings",
                category="candidate-policy-operation-contract",
                details=self.policy._invalid_response_details(text, response),
            )
        try:
            contract = OperationRelevanceContract.from_dict(
                value.get("operation_contract")
            )
        except ValueError as exc:
            raise RecoverablePolicyError(
                f"Invalid operation contract: {exc}",
                category="candidate-policy-operation-contract",
                details=self.policy._invalid_response_details(text, response),
            ) from exc
        context = self.policy._pending_operation_context
        if context is None:
            raise ValueError("Evidence-directed policy has no operation context")
        self.policy._validate_operation_contract(
            contract,
            script,
            self.state,
            context,
        )
        self.contract = contract
        return _ProjectedResponse(
            response,
            json.dumps(
                {"script": script, "rationale": rationale},
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )


class EvidenceDirectedDeploymentPolicy(StructuredModelDeploymentPolicy):
    """Open-program policy with evidence-linked operation relevance."""

    def __init__(
        self,
        *args: Any,
        operation_profile: str = EVIDENCE_DIRECTED_OPERATION_PROFILE,
        **kwargs: Any,
    ) -> None:
        if operation_profile not in {
            EVIDENCE_DIRECTED_OPERATION_PROFILE,
            "free-form",
        }:
            raise ValueError(
                "Evidence-directed policy cannot use another operation profile"
            )
        super().__init__(*args, operation_profile="free-form", **kwargs)
        if self.max_feedback_chars < 8_192:
            raise ValueError(
                "Evidence-directed feedback budget must be at least 8192 characters"
            )
        self._pending_operation_context: dict[str, Any] | None = None

    @staticmethod
    def _goal_finding_id(finding: dict[str, Any], index: int) -> str:
        value = finding.get("finding_id", f"goal-finding-{index:04d}")
        if isinstance(value, str) and value.strip():
            return value
        return f"goal-finding-{index:04d}"

    @classmethod
    def _goal_snapshot_from_verification(
        cls,
        verification: dict[str, Any],
    ) -> dict[str, Any] | None:
        details = verification.get("details")
        if not isinstance(details, dict):
            return None
        diagnostic = details.get("verifier_details", details)
        if not isinstance(diagnostic, dict):
            return None
        report_details = diagnostic.get("report_details", diagnostic)
        if not isinstance(report_details, dict):
            return None
        report = report_details.get("goal_report")
        findings = report.get("findings") if isinstance(report, dict) else None
        if not isinstance(report, dict) or not isinstance(findings, list):
            return None
        normalized_findings = []
        dispositions: dict[str, str] = {}
        for index, raw_finding in enumerate(findings):
            if not isinstance(raw_finding, dict):
                continue
            finding = dict(raw_finding)
            finding_id = cls._goal_finding_id(finding, index)
            finding["finding_id"] = finding_id
            observed = finding.get("observed")
            required = finding.get("required")
            disposition = (
                "unknown"
                if observed is None
                else "satisfied"
                if observed == required
                else "active"
            )
            dispositions[finding_id] = disposition
            normalized_findings.append(finding)
        return {
            "verification_id": verification.get("verification_id"),
            "candidate_id": details.get("candidate_id"),
            "reported_passed": details.get("reported_passed"),
            "status": report.get("status"),
            "finding_set_complete": report.get(
                "finding_set_complete",
                diagnostic.get("finding_set_complete", False),
            )
            is True,
            "findings": tuple(normalized_findings),
            "finding_dispositions": dispositions,
        }

    @classmethod
    def _latest_goal_snapshot(
        cls,
        state: EnvironmentState,
    ) -> dict[str, Any] | None:
        for verification in reversed(state.verifications):
            snapshot = cls._goal_snapshot_from_verification(verification)
            if snapshot is not None:
                return snapshot
        return None

    def _initial_goal_target_id(self) -> str:
        contract_id = (
            self.goal_contract.get("contract_id")
            if isinstance(self.goal_contract, dict)
            else None
        )
        if not isinstance(contract_id, str) or not contract_id.strip():
            contract_id = "environment-ready"
        return f"goal:{contract_id}"

    @staticmethod
    def _reference_id(prefix: str, value: Any) -> str:
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]
        return f"{prefix}:{digest}"

    @staticmethod
    def _operation_contract_from_action(
        action: dict[str, Any],
    ) -> OperationRelevanceContract | None:
        metadata = action.get("metadata")
        value = (
            metadata.get("operation_contract")
            if isinstance(metadata, dict)
            else None
        )
        try:
            return OperationRelevanceContract.from_dict(value)
        except ValueError:
            return None

    @classmethod
    def _conclusive_goal_failures(
        cls,
        state: EnvironmentState,
    ) -> dict[str, dict[str, Any]]:
        failures: dict[str, dict[str, Any]] = {}
        for verification in state.verifications:
            snapshot = cls._goal_snapshot_from_verification(verification)
            if (
                snapshot is None
                or snapshot["status"] != "fail"
                or snapshot["reported_passed"] is not False
            ):
                continue
            candidate_id = snapshot.get("candidate_id")
            if isinstance(candidate_id, str) and candidate_id:
                failures[candidate_id] = {
                    "verification_id": snapshot.get("verification_id"),
                    "finding_set_complete": snapshot[
                        "finding_set_complete"
                    ],
                }
        return failures

    @classmethod
    def _operation_progress(
        cls,
        state: EnvironmentState,
    ) -> dict[str, Any] | None:
        for verification in reversed(state.verifications):
            details = verification.get("details")
            candidate_id = (
                details.get("candidate_id")
                if isinstance(details, dict)
                else None
            )
            action = (
                state.actions.get(candidate_id)
                if isinstance(candidate_id, str)
                else None
            )
            if not isinstance(action, dict):
                continue
            contract = cls._operation_contract_from_action(action)
            if contract is None:
                continue
            metadata = action.get("metadata")
            metadata = metadata if isinstance(metadata, dict) else {}
            before_raw = metadata.get(
                "operation_active_target_ids_before",
                list(contract.target_finding_ids),
            )
            before = (
                {
                    item
                    for item in before_raw
                    if isinstance(item, str)
                }
                if isinstance(before_raw, list)
                else set(contract.target_finding_ids)
            )
            expected = set(contract.expected_resolved_finding_ids)
            snapshot = cls._goal_snapshot_from_verification(verification)
            progress: dict[str, Any] = {
                "contract_id": contract.contract_id,
                "operation_family_id": contract.operation_family.family_id,
                "candidate_id": candidate_id,
                "verification_id": verification.get("verification_id"),
                "active_finding_ids_before": sorted(before),
                "expected_resolved_finding_ids": sorted(expected),
                "conclusive": False,
                "status": "unknown",
                "observed_active_finding_ids": [],
                "observed_resolved_finding_ids": [],
                "expected_still_active_finding_ids": [],
                "unexpected_new_finding_ids": [],
            }
            if verification.get("passed") is True:
                progress.update(
                    {
                        "conclusive": True,
                        "status": "met",
                        "observed_resolved_finding_ids": sorted(expected),
                    }
                )
                return progress
            if snapshot is None:
                return progress
            active_after = {
                finding_id
                for finding_id, disposition in snapshot[
                    "finding_dispositions"
                ].items()
                if disposition == "active"
            }
            progress["observed_active_finding_ids"] = sorted(active_after)
            progress["unexpected_new_finding_ids"] = sorted(
                active_after - before
            )
            if not snapshot["finding_set_complete"]:
                return progress
            synthetic = {
                item for item in expected if item.startswith("goal:")
            }
            ordinary = expected - synthetic
            resolved = ordinary - active_after
            still_active = (ordinary & active_after) | synthetic
            progress.update(
                {
                    "conclusive": True,
                    "status": "met" if not still_active else "not_met",
                    "observed_resolved_finding_ids": sorted(resolved),
                    "expected_still_active_finding_ids": sorted(still_active),
                }
            )
            return progress
        return None

    def _operation_evidence_references(
        self,
        projection: dict[str, Any],
    ) -> list[dict[str, Any]]:
        references: dict[str, dict[str, Any]] = {}

        def add(kind: str, identity: Any, summary: str) -> None:
            evidence_id = self._reference_id(kind, identity)
            references.setdefault(
                evidence_id,
                {
                    "evidence_id": evidence_id,
                    "kind": kind,
                    "summary": self._bounded_value(summary, 240),
                },
            )

        goal = projection.get("goal")
        if isinstance(goal, dict):
            add("goal_contract", goal, "Public executable goal and goal state")
        repository_profile = projection.get("repository_profile")
        if isinstance(repository_profile, dict):
            add(
                "repository_profile",
                repository_profile,
                "Public repository profile for initial deployment planning",
            )
        feedback = projection.get("verification_feedback")
        if isinstance(feedback, list):
            for item in feedback:
                if not isinstance(item, dict):
                    continue
                verification_id = item.get("verification_id")
                if not isinstance(verification_id, str) or not verification_id:
                    continue
                add(
                    "execution_feedback",
                    {"verification_id": verification_id},
                    f"{verification_id}: {item.get('summary')}",
                )
        repository_evidence = projection.get("repository_evidence")
        queries = (
            repository_evidence.get("queries")
            if isinstance(repository_evidence, dict)
            else None
        )
        if isinstance(queries, list):
            for query in queries:
                if not isinstance(query, dict):
                    continue
                related = query.get("related_occurrences")
                excerpts = [query.get("target_excerpt")]
                if isinstance(related, list):
                    excerpts.extend(related)
                for excerpt in excerpts:
                    if not isinstance(excerpt, dict):
                        continue
                    path = excerpt.get("path")
                    source_sha256 = excerpt.get("source_sha256")
                    if not isinstance(path, str) or not isinstance(
                        source_sha256, str
                    ):
                        continue
                    identity = {
                        "path": path,
                        "source_sha256": source_sha256,
                        "start_line": excerpt.get("start_line"),
                        "end_line": excerpt.get("end_line"),
                    }
                    add(
                        "repository_evidence",
                        identity,
                        (
                            f"{path}:{excerpt.get('start_line')}-"
                            f"{excerpt.get('end_line')} for "
                            f"{query.get('subject')}"
                        ),
                    )
        anchor = projection.get("retained_candidate_anchor")
        if isinstance(anchor, dict):
            candidate = anchor.get("candidate")
            if isinstance(candidate, dict):
                candidate_id = candidate.get("candidate_id")
                script = candidate.get("script")
                if isinstance(candidate_id, str) and isinstance(script, str):
                    add(
                        "candidate_anchor",
                        {
                            "candidate_id": candidate_id,
                            "script_sha256": hashlib.sha256(
                                script.encode("utf-8")
                            ).hexdigest(),
                        },
                        f"Retained admissible candidate {candidate_id}",
                    )
        priority = {
            "execution_feedback": 0,
            "repository_evidence": 1,
            "candidate_anchor": 2,
            "repository_profile": 3,
            "goal_contract": 4,
        }
        return sorted(
            references.values(),
            key=lambda item: (
                priority.get(str(item["kind"]), 99),
                str(item["evidence_id"]),
            ),
        )

    def _operation_context(
        self,
        state: EnvironmentState,
        projection: dict[str, Any],
        *,
        max_chars: int,
    ) -> dict[str, Any]:
        snapshot = self._latest_goal_snapshot(state)
        active_findings = (
            [
                finding
                for finding in snapshot["findings"]
                if snapshot["finding_dispositions"].get(
                    finding["finding_id"]
                )
                == "active"
            ]
            if snapshot is not None
            else []
        )
        active_findings.sort(key=lambda item: item["finding_id"])
        targets = [
            {
                "finding_id": finding["finding_id"],
                "domain": finding.get("domain"),
                "subject": finding.get("subject"),
                "predicate": finding.get("predicate"),
                "source_file": (
                    finding.get("provenance", {}).get("file")
                    if isinstance(finding.get("provenance"), dict)
                    else None
                ),
            }
            for finding in active_findings[:24]
        ]
        if not targets:
            description = (
                self.goal_contract.get("description")
                if isinstance(self.goal_contract, dict)
                else None
            )
            targets = [
                {
                    "finding_id": self._initial_goal_target_id(),
                    "domain": "goal",
                    "subject": description
                    or "Construct an executable project environment",
                    "predicate": "satisfied",
                    "source_file": None,
                }
            ]
        progress = self._operation_progress(state)
        context = {
            "schema": OPERATION_RELEVANCE_CONTEXT_SCHEMA,
            "active_target_count": len(active_findings) or 1,
            "omitted_target_count": max(len(active_findings) - len(targets), 0),
            "target_set_complete": (
                snapshot["finding_set_complete"]
                if snapshot is not None
                else False
            ),
            "source_verification_id": (
                snapshot.get("verification_id")
                if snapshot is not None
                else None
            ),
            "active_targets": targets,
            "available_precondition_evidence": (
                self._operation_evidence_references(projection)[:24]
            ),
            "previous_progress": (
                self._bounded_json_value(progress, 1_400)
                if progress is not None
                else None
            ),
        }
        while (
            self._json_size(context) > max_chars
            and len(context["available_precondition_evidence"]) > 1
        ):
            context["available_precondition_evidence"].pop()
        while (
            self._json_size(context) > max_chars
            and len(context["active_targets"]) > 1
        ):
            context["active_targets"].pop()
            context["omitted_target_count"] += 1
        if self._json_size(context) > max_chars:
            context["previous_progress"] = None
        if self._json_size(context) > max_chars:
            raise ValueError(
                "Operation relevance context exceeds its model-input budget"
            )
        return context

    def _state_projection(self, state: EnvironmentState) -> dict[str, Any]:
        full_limit = self.max_feedback_chars
        context_limit = max(2_048, int(full_limit * 0.12))
        self.max_feedback_chars = full_limit - context_limit - 128
        try:
            projection = super()._state_projection(state)
        finally:
            self.max_feedback_chars = full_limit
        context = self._operation_context(
            state,
            projection,
            max_chars=context_limit,
        )
        projection["operation_context"] = context
        if self._json_size(projection) > self.max_feedback_chars:
            raise ValueError(
                "Bounded solver feedback exceeds the model context contract"
            )
        self._pending_operation_context = context
        return projection

    def _validate_operation_contract(
        self,
        contract: OperationRelevanceContract,
        script: str,
        state: EnvironmentState,
        context: dict[str, Any],
    ) -> None:
        active_target_ids = {
            item["finding_id"]
            for item in context["active_targets"]
            if isinstance(item, dict)
            and isinstance(item.get("finding_id"), str)
        }
        unknown_targets = sorted(
            set(contract.target_finding_ids) - active_target_ids
        )
        if unknown_targets:
            raise RecoverablePolicyError(
                "Operation contract targets findings that are not active",
                category="candidate-policy-operation-contract",
                details={
                    "reason_code": "unknown-target",
                    "unknown_target_ids": unknown_targets,
                    "active_target_ids": sorted(active_target_ids),
                },
            )
        evidence_by_id = {
            item["evidence_id"]: item
            for item in context["available_precondition_evidence"]
        }
        unknown_evidence = sorted(
            set(contract.precondition_evidence_ids)
            - set(evidence_by_id)
        )
        if unknown_evidence:
            raise RecoverablePolicyError(
                "Operation contract cites evidence not exposed to the model",
                category="candidate-policy-operation-contract",
                details={
                    "reason_code": "unknown-evidence",
                    "unknown_evidence_ids": unknown_evidence,
                },
            )
        if not all(
            target.startswith("goal:")
            for target in contract.target_finding_ids
        ):
            concrete_kinds = {
                "execution_feedback",
                "repository_evidence",
                "candidate_anchor",
            }
            if not any(
                evidence_by_id[evidence_id]["kind"] in concrete_kinds
                for evidence_id in contract.precondition_evidence_ids
            ):
                raise RecoverablePolicyError(
                    "Finding-directed repair lacks concrete precondition evidence",
                    category="candidate-policy-operation-contract",
                    details={
                        "reason_code": "ungrounded-precondition",
                        "required_evidence_kinds": sorted(concrete_kinds),
                    },
                )

        failures = self._conclusive_goal_failures(state)
        script_sha256 = hashlib.sha256(script.encode("utf-8")).hexdigest()
        for candidate_id in failures:
            action = state.actions.get(candidate_id)
            previous_script = (
                action.get("command")
                if isinstance(action, dict)
                else None
            )
            if (
                isinstance(previous_script, str)
                and hashlib.sha256(
                    previous_script.encode("utf-8")
                ).hexdigest()
                == script_sha256
            ):
                raise RecoverablePolicyError(
                    "Candidate repeats a conclusively failed complete script",
                    category="candidate-policy-operation-contract",
                    details={
                        "reason_code": "repeated-failed-script",
                        "source_candidate_id": candidate_id,
                        "script_sha256": script_sha256,
                    },
                )

        current_evidence = set(contract.precondition_evidence_ids)
        current_targets = set(contract.target_finding_ids)
        for candidate_id, failure in failures.items():
            action = state.actions.get(candidate_id)
            if not isinstance(action, dict):
                continue
            previous = self._operation_contract_from_action(action)
            if (
                previous is None
                or previous.operation_family.family_id
                != contract.operation_family.family_id
                or not (
                    current_targets & set(previous.target_finding_ids)
                )
            ):
                continue
            newly_cited = current_evidence - set(
                previous.precondition_evidence_ids
            )
            if newly_cited:
                continue
            raise RecoverablePolicyError(
                "Candidate repeats a failed operation family without new evidence",
                category="candidate-policy-operation-contract",
                details={
                    "reason_code": "repeated-family-without-new-evidence",
                    "source_candidate_id": candidate_id,
                    "source_verification_id": failure[
                        "verification_id"
                    ],
                    "operation_family_id": (
                        contract.operation_family.family_id
                    ),
                },
            )

    def propose(self, state: EnvironmentState) -> DeploymentCandidate:
        original_model = self.model
        proxy = _EvidenceDirectedModelProxy(self, original_model, state)
        self.model = proxy
        try:
            candidate = super().propose(state)
        finally:
            self.model = original_model
        contract = proxy.contract
        context = self._pending_operation_context
        if contract is None or context is None:
            raise ValueError("Evidence-directed candidate contract was not retained")
        metadata = {
            **candidate.metadata,
            "generator": "evidence-directed-model-policy-v1",
            "operation_profile": EVIDENCE_DIRECTED_OPERATION_PROFILE,
            "operation_contract": contract.semantic_dict(),
            "operation_contract_id": contract.contract_id,
            "operation_family_id": contract.operation_family.family_id,
            "operation_active_target_ids_before": [
                item["finding_id"] for item in context["active_targets"]
            ],
            "operation_target_set_complete_before": context[
                "target_set_complete"
            ],
            "operation_context_schema": OPERATION_RELEVANCE_CONTEXT_SCHEMA,
        }
        return replace(candidate, metadata=metadata)
