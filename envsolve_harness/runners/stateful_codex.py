from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any

from envsolve.constraints import build_model_goal_obligation_frontier
from envsolve.runtime.docker import DockerFreshEnvironmentProvider
from envsolve.runtime.goal_verifier import ExecutableGoalContractVerifier
from envsolve.runtime.stateful_goal_verifier_v2 import (
    StatefulExecutableGoalVerifierV2,
    StatefulExecutableGoalVerifierV21,
)
from envsolve.runtime.stateful_goal_verifier_v22 import (
    StatefulExecutableGoalVerifierV22,
)
from envsolve.runtime.stateful_goal_verifier_v23 import (
    StatefulExecutableGoalVerifierV23,
)
from envsolve.runtime.stateful_goal_verifier_v24 import (
    StatefulExecutableGoalVerifierV24,
)
from envsolve.solver import (
    DeploymentCandidate,
    EpisodeBudgetExhausted,
    RecoverablePolicyError,
)
from envsolve.state import EnvironmentState
from envsolve_harness.core.io import (
    read_json,
    read_jsonl,
    write_json,
    write_text_atomic,
)
from envsolve_harness.core.models import Case, RunSpec, SolverResult
from envsolve_harness.execution.batch import (
    cleanup_case_containers,
    terminate_process_group,
)
from envsolve_harness.integrity.repository import inspect_repository
from envsolve_harness.runners.codex_cli import (
    OUTPUT_SCHEMA,
    CodexCliRunner,
    parse_codex_usage,
)
from envsolve_harness.runners.envsolve import EnvSolveEpisodeRunner
from envsolve_harness.scripts.open_program import OpenCandidateProgramValidator
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import update_manifest
from envsolve_harness.utils.provenance import sha256_file


STRUCTURED_METHOD = "envsolve-pro-stateful-agent-v1"
RAW_HISTORY_METHOD = "codex-cli-goal-aware-raw-repair"
STRUCTURED_METHOD_V2 = "envsolve-pro-stateful-agent-v2"
RAW_HISTORY_METHOD_V2 = "codex-cli-goal-aware-raw-repair-v2"
STRUCTURED_METHOD_V21 = "envsolve-pro-stateful-agent-v2.1"
RAW_HISTORY_METHOD_V21 = "codex-cli-goal-aware-raw-repair-v2.1"
STRUCTURED_METHOD_V22 = "envsolve-pro-stateful-agent-v2.2"
RAW_HISTORY_METHOD_V22 = "codex-cli-goal-aware-raw-repair-v2.2"
STRUCTURED_METHOD_V23 = "envsolve-pro-stateful-agent-v2.3"
RAW_HISTORY_METHOD_V23 = "codex-cli-goal-aware-raw-repair-v2.3"
STRUCTURED_METHOD_V24 = "envsolve-pro-stateful-agent-v2.4"
RAW_HISTORY_METHOD_V24 = "codex-cli-goal-aware-raw-repair-v2.4"
_METHOD_MODES = {
    STRUCTURED_METHOD: "structured",
    RAW_HISTORY_METHOD: "raw",
    STRUCTURED_METHOD_V2: "structured",
    RAW_HISTORY_METHOD_V2: "raw",
    STRUCTURED_METHOD_V21: "structured",
    RAW_HISTORY_METHOD_V21: "raw",
    STRUCTURED_METHOD_V22: "structured",
    RAW_HISTORY_METHOD_V22: "raw",
    STRUCTURED_METHOD_V23: "structured",
    RAW_HISTORY_METHOD_V23: "raw",
    STRUCTURED_METHOD_V24: "structured",
    RAW_HISTORY_METHOD_V24: "raw",
}
_V2_METHODS = frozenset({STRUCTURED_METHOD_V2, RAW_HISTORY_METHOD_V2})
_V21_METHODS = frozenset({STRUCTURED_METHOD_V21, RAW_HISTORY_METHOD_V21})
_V22_METHODS = frozenset({STRUCTURED_METHOD_V22, RAW_HISTORY_METHOD_V22})
_V23_METHODS = frozenset({STRUCTURED_METHOD_V23, RAW_HISTORY_METHOD_V23})
_V24_METHODS = frozenset({STRUCTURED_METHOD_V24, RAW_HISTORY_METHOD_V24})


def _tail(value: object, limit: int) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= limit else text[-limit:]


def _recent_actions(state: EnvironmentState) -> list[dict[str, Any]]:
    ordered = sorted(
        state.actions.values(),
        key=lambda item: int(item.get("state_metadata", {}).get("event_sequence", 0)),
    )[-2:]
    return [
        {
            "candidate_id": item.get("action_id"),
            "script": _tail(item.get("command"), 16_000),
            "status": item.get("status"),
            "exit_code": item.get("exit_code"),
            "stderr_tail": _tail(
                (item.get("observation") or {}).get("stderr")
                if isinstance(item.get("observation"), dict)
                else "",
                6000,
            ),
            "diagnostic_workspace_integrity": (
                item.get("metadata", {}).get("diagnostic_workspace_integrity")
                if isinstance(item.get("metadata"), dict)
                else None
            ),
        }
        for item in ordered
    ]


def _recent_failures(state: EnvironmentState) -> list[dict[str, Any]]:
    ordered = sorted(
        state.failures.values(),
        key=lambda item: int(item.get("state_metadata", {}).get("event_sequence", 0)),
    )[-3:]
    return [
        {
            "category": item.get("category"),
            "message": _tail(item.get("message"), 6000),
            "action_id": item.get("action_id"),
            "details": item.get("details"),
        }
        for item in ordered
    ]


def _recent_verifications(state: EnvironmentState) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for item in state.verifications[-2:]:
        details = item.get("details")
        details = details if isinstance(details, dict) else {}
        verifier_details = details.get("verifier_details")
        verifier_details = (
            verifier_details if isinstance(verifier_details, dict) else {}
        )
        values.append(
            {
                "verification_id": item.get("verification_id"),
                "candidate_id": details.get("candidate_id"),
                "passed": item.get("passed"),
                "reported_passed": details.get("reported_passed"),
                "bootstrap_exit_code": details.get("bootstrap_exit_code"),
                "summary": details.get("summary"),
                "goal_report": verifier_details.get("goal_report"),
                "candidate_assessment": details.get("candidate_assessment"),
            }
        )
    return values


def _compact_recent_failures(state: EnvironmentState) -> list[dict[str, Any]]:
    ordered = sorted(
        state.failures.values(),
        key=lambda item: int(item.get("state_metadata", {}).get("event_sequence", 0)),
    )[-2:]
    values: list[dict[str, Any]] = []
    for item in ordered:
        details = item.get("details")
        details = details if isinstance(details, dict) else {}
        report_details = details.get("report_details")
        report_details = report_details if isinstance(report_details, dict) else {}
        values.append(
            {
                "category": item.get("category"),
                "message": _tail(item.get("message"), 2000),
                "action_id": item.get("action_id"),
                "verifier_summary": {
                    "adapter_schema": details.get("adapter_schema"),
                    "completed": details.get("completed"),
                    "goal_passed": details.get("goal_passed"),
                    "infrastructure_error": details.get("infrastructure_error"),
                    "finding_set_complete": details.get("finding_set_complete"),
                    "constraint_compaction": report_details.get(
                        "constraint_compaction"
                    ),
                },
            }
        )
    return values


def _compact_recent_verifications(
    state: EnvironmentState,
) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for item in state.verifications[-2:]:
        details = item.get("details")
        details = details if isinstance(details, dict) else {}
        verifier_details = details.get("verifier_details")
        verifier_details = (
            verifier_details if isinstance(verifier_details, dict) else {}
        )
        report_details = verifier_details.get("report_details")
        report_details = report_details if isinstance(report_details, dict) else {}
        values.append(
            {
                "verification_id": item.get("verification_id"),
                "candidate_id": details.get("candidate_id"),
                "passed": item.get("passed"),
                "reported_passed": details.get("reported_passed"),
                "bootstrap_exit_code": details.get("bootstrap_exit_code"),
                "summary": _tail(details.get("summary"), 2000),
                "counterexample_count": details.get("counterexample_count"),
                "candidate_assessment": details.get("candidate_assessment"),
                "constraint_compaction": report_details.get(
                    "constraint_compaction"
                ),
            }
        )
    return values


def _operation_state(state: EnvironmentState) -> dict[str, Any] | None:
    for item in reversed(state.verifications):
        details = item.get("details")
        details = details if isinstance(details, dict) else {}
        verifier_details = details.get("verifier_details")
        verifier_details = (
            verifier_details if isinstance(verifier_details, dict) else {}
        )
        contract = verifier_details.get("operation_contract")
        if not isinstance(contract, dict):
            continue
        violations = contract.get("violations")
        violations = violations if isinstance(violations, list) else []
        return {
            "candidate_id": details.get("candidate_id"),
            "goal_status": contract.get("goal_status"),
            "operation_status": contract.get("status"),
            "operation_valid": contract.get("valid"),
            "repository_effect_valid": contract.get(
                "repository_effect_valid"
            ),
            "shell_postconditions": contract.get("shell_postconditions"),
            "violations": violations[:20],
            "violation_count": len(violations),
            "violations_omitted": max(0, len(violations) - 20),
        }
    return None


def _best_candidate(state: EnvironmentState) -> dict[str, Any] | None:
    best: tuple[tuple[int, int, int], str, dict[str, Any]] | None = None
    for position, item in enumerate(state.verifications, start=1):
        details = item.get("details")
        if not isinstance(details, dict):
            continue
        assessment = details.get("candidate_assessment")
        candidate_id = details.get("candidate_id")
        if (
            not isinstance(assessment, dict)
            or assessment.get("admissible") is not True
            or not isinstance(candidate_id, str)
            or candidate_id not in state.actions
        ):
            continue
        unresolved = assessment.get("unresolved_constraints")
        satisfied = assessment.get("satisfied_constraints")
        if (
            isinstance(unresolved, bool)
            or not isinstance(unresolved, int)
            or isinstance(satisfied, bool)
            or not isinstance(satisfied, int)
        ):
            continue
        rank = (unresolved, -satisfied, position)
        if best is None or rank < best[0]:
            best = (rank, candidate_id, assessment)
    if best is None:
        return None
    rank, candidate_id, assessment = best
    action = state.actions[candidate_id]
    return {
        "candidate_id": candidate_id,
        "script": _tail(action.get("command"), 24_000),
        "assessment": assessment,
        "selection_rank": list(rank),
    }


def state_projection(
    state: EnvironmentState,
    mode: str,
    *,
    compact: bool = False,
    operation_feedback: bool = False,
) -> dict[str, Any]:
    prior_candidates = _recent_actions(state)
    if compact:
        prior_candidates = prior_candidates[-1:]
    common = {
        "schema": (
            "envsolve-agent-state-v3"
            if mode == "structured" and compact and operation_feedback
            else "envsolve-agent-state-v2"
            if mode == "structured" and compact
            else "envsolve-agent-state-v1"
            if mode == "structured"
            else "envsolve-agent-raw-feedback-v1"
        ),
        "case": state.case,
        "prior_candidates": prior_candidates,
        "recent_failures": (
            _compact_recent_failures(state)
            if compact
            else _recent_failures(state)
        ),
        "recent_verifications": (
            _compact_recent_verifications(state)
            if compact
            else _recent_verifications(state)
        ),
    }
    if mode == "raw":
        return common
    if mode != "structured":
        raise ValueError(f"Unsupported stateful-agent mode: {mode}")
    best = _best_candidate(state)
    if (
        compact
        and best is not None
        and any(
            item.get("candidate_id") == best["candidate_id"]
            for item in prior_candidates
        )
    ):
        best = {
            key: value
            for key, value in best.items()
            if key != "script"
        }
        best["script_ref"] = "prior_candidates"
    projection = {
        **common,
        "active_goal_state": build_model_goal_obligation_frontier(
            state,
            max_chars=16_000,
        ),
        "best_integrity_valid_candidate": best,
    }
    if operation_feedback:
        projection["operation_state"] = _operation_state(state)
    return projection


class ExecutionOnlyBudget:
    """Safety controls for executions; model usage remains an outcome metric."""

    def __init__(self, max_items: int, wall_clock_seconds: int) -> None:
        self.max_items = max_items
        self.wall_clock_seconds = wall_clock_seconds
        self.started = time.monotonic()
        self.candidates: list[str] = []
        self.environments: list[str] = []
        self.commands: list[str] = []

    def _reserve(self, target: list[str], scope: str, candidate_id: str) -> None:
        if time.monotonic() - self.started >= self.wall_clock_seconds:
            raise EpisodeBudgetExhausted("wall_clock_seconds")
        if len(target) >= self.max_items:
            raise EpisodeBudgetExhausted(scope)
        target.append(candidate_id)

    def reserve_candidate(self, candidate_id: str) -> None:
        self._reserve(self.candidates, "candidates", candidate_id)

    def reserve_environment(self, candidate_id: str) -> None:
        self._reserve(self.environments, "environments", candidate_id)

    def reserve_command(self, candidate_id: str) -> None:
        self._reserve(self.commands, "commands", candidate_id)

    def snapshot(self) -> dict[str, Any]:
        return {
            "policy": "execution-safety-only-v1",
            "limits": {
                "max_candidates": self.max_items,
                "max_environments": self.max_items,
                "max_commands": self.max_items,
                "wall_clock_seconds": self.wall_clock_seconds,
            },
            "usage": {
                "candidates": len(self.candidates),
                "environments": len(self.environments),
                "commands": len(self.commands),
                "elapsed_wall_clock_seconds": time.monotonic() - self.started,
            },
            "model_tokens_are_hard_limit": False,
            "model_cost_is_hard_limit": False,
        }


class CodexInteractivePolicy:
    """Use independent Codex sessions as the open Operation layer."""

    def __init__(
        self,
        *,
        runner: CodexCliRunner,
        case: Case,
        run_spec: RunSpec,
        container_id: str,
        workspace: Path,
        rounds_root: Path,
        feedback_mode: str,
        max_rounds: int,
        deadline: float,
        initial_probe: bool = False,
        compact_projection: bool = False,
        operation_feedback: bool = False,
    ) -> None:
        self.runner = runner
        self.case = case
        self.run_spec = run_spec
        self.container_id = container_id
        self.workspace = workspace
        self.rounds_root = rounds_root
        self.feedback_mode = feedback_mode
        self.max_rounds = max_rounds
        self.deadline = deadline
        self.round_count = 0
        self.initial_probe = initial_probe
        self.compact_projection = compact_projection
        self.operation_feedback = operation_feedback
        self.initial_probe_submitted = False
        self.total_usage: dict[str, int] = {}
        self.total_container_commands = 0
        self.round_summaries: list[dict[str, Any]] = []

    def _prompt(self, projection: dict[str, Any]) -> str:
        encoded = json.dumps(projection, ensure_ascii=True, indent=2, sort_keys=True)
        operation_instruction = (
            "\nThe structured state separates executable-goal status from "
            "caller-visible operation postconditions. If the goal is already "
            "satisfied, preserve that construction and repair only the exact "
            "operation violations.\n"
            if self.operation_feedback
            else ""
        )
        return (
            self.runner._prompt(self.case, self.runner.goal_contract)
            + "\n"
            + f"""\
This is operation round {self.round_count}. The state below contains only
repository evidence and prior internal execution feedback; it contains no
official evaluator result. The diagnostic container persists across rounds, but
this Codex session has no prior conversation. Inspect the current workspace,
repair the deployment, and submit one cumulative program for a fresh checkout.
Treat candidate-policy and repository-effect failures as hard admissibility
feedback. Do not repeat a rejected program without correcting its stated cause.
{operation_instruction}

<solver_state mode="{self.feedback_mode}">
{encoded}
</solver_state>
"""
        )

    def _record_usage(self, usage: dict[str, int]) -> None:
        for name, value in usage.items():
            self.total_usage[name] = self.total_usage.get(name, 0) + value

    def _invoke(self, projection: dict[str, Any]) -> dict[str, Any]:
        self.round_count += 1
        if self.round_count > self.max_rounds:
            raise EpisodeBudgetExhausted("agent_rounds")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise EpisodeBudgetExhausted("wall_clock_seconds")
        root = self.rounds_root / f"round-{self.round_count:04d}"
        root.mkdir(parents=True, exist_ok=False)
        schema_path = root / "output-schema.json"
        output_path = root / "final-output.json"
        events_path = root / "events.jsonl"
        trace_path = root / "container-commands.jsonl"
        prompt_path = root / "prompt.txt"
        projection_path = root / "state-projection.json"
        write_json(schema_path, OUTPUT_SCHEMA)
        write_json(projection_path, projection)
        write_text_atomic(prompt_path, self._prompt(projection))
        command = self.runner._codex_command(
            run_spec=self.run_spec,
            control_dir=root,
            schema_path=schema_path,
            output_path=output_path,
            trace_path=trace_path,
            container_id=self.container_id,
        )
        process_env = os.environ.copy()
        for name in (
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENROUTER_API_KEY",
            "ANTHROPIC_API_KEY",
        ):
            process_env.pop(name, None)
        process = subprocess.Popen(
            command,
            cwd=self.runner.harness_root,
            env=process_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        timed_out = False
        try:
            stdout, stderr = process.communicate(
                input=prompt_path.read_text(encoding="utf-8"),
                timeout=max(1, int(remaining)),
            )
        except subprocess.TimeoutExpired:
            timed_out = True
            terminate_process_group(process)
            stdout, stderr = process.communicate()
        write_text_atomic(events_path, stdout)
        try:
            records = read_jsonl(events_path)
            event_parse_error = None
        except ValueError as exc:
            records = []
            event_parse_error = str(exc)
        command_records = read_jsonl(trace_path) if trace_path.is_file() else []
        successful_commands = sum(
            1
            for item in command_records
            if item.get("exit_code") == 0
            and not item.get("timed_out")
            and not item.get("infrastructure_error")
        )
        usage = parse_codex_usage(records)
        self._record_usage(usage)
        self.total_container_commands += len(command_records)
        integrity = inspect_repository(
            self.workspace,
            self.case.revision,
            required_preconditions=self.runner.workspace_preconditions,
        ).to_dict()
        write_json(root / "repository-integrity.json", integrity)
        summary = {
            "round": self.round_count,
            "process_exit_code": process.returncode,
            "timed_out": timed_out,
            "event_parse_error": event_parse_error,
            "token_usage": usage,
            "container_command_count": len(command_records),
            "successful_container_command_count": successful_commands,
            "prompt_sha256": sha256_file(prompt_path),
            "projection_sha256": sha256_file(projection_path),
            "events_sha256": sha256_file(events_path),
            "trace_sha256": (
                sha256_file(trace_path) if trace_path.is_file() else None
            ),
            "diagnostic_workspace_integrity_valid": integrity.get("valid"),
            "stdout_tail": _tail(stdout, 8000),
            "stderr_tail": _tail(stderr, 8000),
        }
        self.round_summaries.append(summary)
        write_json(root / "process-result.json", summary)
        if timed_out:
            raise EpisodeBudgetExhausted("wall_clock_seconds")
        if process.returncode != 0:
            raise RuntimeError(f"Codex operation round exited with {process.returncode}")
        if successful_commands == 0:
            raise RecoverablePolicyError(
                "Codex operation round completed without a successful terminal command",
                category="candidate-policy-agent-no-execution",
                details={"round": self.round_count},
            )
        if not output_path.is_file():
            raise RecoverablePolicyError(
                "Codex operation round did not produce structured final output",
                category="candidate-policy-agent-submission",
                details={"round": self.round_count},
            )
        submission = read_json(output_path)
        if not isinstance(submission, dict) or not isinstance(
            submission.get("bootstrap_script"), str
        ):
            raise RecoverablePolicyError(
                "Codex final output does not match the bootstrap schema",
                category="candidate-policy-agent-submission",
                details={"round": self.round_count},
            )
        return {
            **submission,
            "diagnostic_workspace_integrity": {
                "valid": integrity.get("valid"),
                "policy": integrity.get("policy"),
                "tracked_changes": list(integrity.get("tracked_changes", []))[:50],
                "disallowed_untracked_paths": list(
                    integrity.get("disallowed_untracked_paths", [])
                )[:50],
                "violations": list(integrity.get("violations", []))[:50],
            },
            "projection_sha256": summary["projection_sha256"],
        }

    def propose(self, state: EnvironmentState) -> DeploymentCandidate:
        if self.initial_probe and not self.initial_probe_submitted:
            self.initial_probe_submitted = True
            return DeploymentCandidate(
                candidate_id="stateful-initial-observation",
                script=":",
                rationale=(
                    "Shared read-only executable-goal observation before the "
                    "first model operation"
                ),
                metadata={
                    "agent_round": 0,
                    "feedback_mode": self.feedback_mode,
                    "execution_role": "initial-observation",
                    "initial_observation": True,
                },
            )
        projection = state_projection(
            state,
            self.feedback_mode,
            compact=self.compact_projection,
            operation_feedback=self.operation_feedback,
        )
        submission = self._invoke(projection)
        script = submission["bootstrap_script"].strip()
        if not script:
            raise RecoverablePolicyError(
                "Codex returned an empty bootstrap program",
                category="candidate-policy-agent-submission",
                details={"round": self.round_count},
            )
        return DeploymentCandidate(
            candidate_id=f"stateful-agent-{self.round_count:04d}",
            script=script,
            rationale=str(submission.get("summary", "Codex operation round")),
            metadata={
                "agent_round": self.round_count,
                "feedback_mode": self.feedback_mode,
                "state_projection_sha256": submission["projection_sha256"],
                "diagnostic_workspace_integrity": submission[
                    "diagnostic_workspace_integrity"
                ],
            },
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "feedback_mode": self.feedback_mode,
            "initial_probe_enabled": self.initial_probe,
            "initial_probe_submitted": self.initial_probe_submitted,
            "compact_projection": self.compact_projection,
            "operation_feedback": self.operation_feedback,
            "rounds_started": self.round_count,
            "token_usage": dict(self.total_usage),
            "container_command_count": self.total_container_commands,
            "rounds": list(self.round_summaries),
        }


class StatefulCodexCliRunner(CodexCliRunner):
    """Connect the Codex Operation layer to the existing EnvSolve state loop."""

    runner_version = "0.6.0"

    def __init__(
        self,
        *,
        max_rounds: int,
        feedback_mode: str,
        method_profile: str = "stateful-agent-v1",
        initial_probe: bool = False,
        enforce_project_namespace_provenance: bool = False,
        restore_shell_invariants: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if max_rounds <= 0:
            raise ValueError("Stateful Codex max_rounds must be positive")
        if feedback_mode not in {"structured", "raw"}:
            raise ValueError("Stateful Codex feedback_mode must be structured or raw")
        if method_profile not in {
            "stateful-agent-v1",
            "stateful-agent-v2",
            "stateful-agent-v2.1",
            "stateful-agent-v2.2",
            "stateful-agent-v2.3",
            "stateful-agent-v2.4",
        }:
            raise ValueError("Unsupported Stateful Codex method profile")
        profile_has_v2_features = method_profile in {
            "stateful-agent-v2",
            "stateful-agent-v2.1",
            "stateful-agent-v2.2",
        }
        if any(
            enabled != profile_has_v2_features
            for enabled in (
                initial_probe,
                enforce_project_namespace_provenance,
                restore_shell_invariants,
            )
        ):
            raise ValueError(
                "Stateful Codex profile and verification features must be version-aligned"
            )
        self.max_rounds = max_rounds
        self.feedback_mode = feedback_mode
        self.method_profile = method_profile
        self.initial_probe = initial_probe
        self.enforce_project_namespace_provenance = (
            enforce_project_namespace_provenance
        )
        self.restore_shell_invariants = restore_shell_invariants

    def _cleanup_diagnostic_container(self, container_id: str) -> None:
        subprocess.run(
            [
                "docker",
                "exec",
                "--user",
                "0:0",
                container_id,
                "chown",
                "-R",
                f"{os.getuid()}:{os.getgid()}",
                "/data/project",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        subprocess.run(
            ["docker", "rm", "-f", container_id],
            capture_output=True,
            text=True,
            check=False,
        )

    def _setup_failure(
        self,
        artifacts: RunArtifacts,
        run_spec: RunSpec,
        metadata: dict[str, Any],
        message: str,
    ) -> SolverResult:
        return self._finish(
            artifacts,
            SolverResult(
                False,
                run_spec.method,
                error=message,
                metadata={**metadata, "finished_at": self._now()},
            ),
            message + "\n",
        )

    def run(self, case: Case, artifacts: RunArtifacts, run_spec: RunSpec) -> SolverResult:
        started_at = self._now()
        expected_mode = _METHOD_MODES.get(run_spec.method)
        launcher: dict[str, Any] = {
            "runner": "stateful-codex-cli",
            "runner_version": self.runner_version,
            "method_profile": self.method_profile,
            "feedback_mode": self.feedback_mode,
            "initial_probe": self.initial_probe,
            "project_namespace_provenance": (
                self.enforce_project_namespace_provenance
            ),
            "project_module_identity_provenance": (
                self.method_profile == "stateful-agent-v2.2"
            ),
            "constraint_authority": (
                "official-goal+shared-protocol-only"
                if self.method_profile
                in {"stateful-agent-v2.3", "stateful-agent-v2.4"}
                else "legacy-profile"
            ),
            "finding_projection": (
                "root-obligation-v1"
                if self.method_profile
                in {"stateful-agent-v2.3", "stateful-agent-v2.4"}
                and self.feedback_mode == "structured"
                else self.feedback_mode
            ),
            "operation_postconditions": (
                "repository-effects+caller-working-directory-v1"
                if self.method_profile == "stateful-agent-v2.4"
                else None
            ),
            "restore_shell_invariants": self.restore_shell_invariants,
            "official_evaluator_access": "post-episode-only",
            "online_feedback": "public-goal+candidate-policy+effect-audit",
            "max_rounds": self.max_rounds,
            "resource_policy": {
                "generation_wall_clock_safety_cap_seconds": self.timeout,
                "container_command_safety_cap_seconds": self.command_timeout,
                "token_usage_is_hard_limit": False,
                "cost_is_hard_limit": False,
            },
            "started_at": started_at,
        }
        if expected_mode != self.feedback_mode:
            return self._setup_failure(
                artifacts,
                run_spec,
                launcher,
                f"Unsupported stateful Codex method {run_spec.method!r}",
            )
        expected_v2 = run_spec.method in _V2_METHODS
        expected_v21 = run_spec.method in _V21_METHODS
        expected_v22 = run_spec.method in _V22_METHODS
        expected_v23 = run_spec.method in _V23_METHODS
        expected_v24 = run_spec.method in _V24_METHODS
        expected_profile = (
            "stateful-agent-v2.4"
            if expected_v24
            else "stateful-agent-v2.3"
            if expected_v23
            else "stateful-agent-v2.2"
            if expected_v22
            else "stateful-agent-v2.1"
            if expected_v21
            else "stateful-agent-v2"
            if expected_v2
            else "stateful-agent-v1"
        )
        if self.method_profile != expected_profile:
            return self._setup_failure(
                artifacts,
                run_spec,
                launcher,
                f"Stateful Codex profile does not match method {run_spec.method!r}",
            )
        if self.goal_contract is None:
            return self._setup_failure(
                artifacts,
                run_spec,
                launcher,
                "Stateful Codex requires a public executable goal",
            )
        if not run_spec.model:
            return self._setup_failure(
                artifacts,
                run_spec,
                launcher,
                "Stateful Codex requires RunSpec.model",
            )
        if not self.codex_executable.is_file():
            return self._setup_failure(
                artifacts,
                run_spec,
                launcher,
                f"Codex CLI executable is missing: {self.codex_executable}",
            )

        workspace = artifacts.generation_dir / "diagnostic-workspace"
        rounds_root = artifacts.generation_dir / "agent-rounds"
        replays_root = artifacts.generation_dir / "fresh-replays"
        rounds_root.mkdir(parents=True, exist_ok=True)
        container_id: str | None = None
        policy: CodexInteractivePolicy | None = None
        execution_limit = self.max_rounds + (1 if self.initial_probe else 0)
        budget = ExecutionOnlyBudget(execution_limit, self.timeout)
        try:
            acquisition_commands = self._acquire_repository(case, workspace)
            self._materialize_workspace_preconditions(workspace)
            image_digest = self._image_digest()
            container_id = self._create_container(workspace, image_digest)
            version = subprocess.run(
                [str(self.codex_executable), "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            launcher.update(
                {
                    "repository_acquisition": {
                        "source": "github-exact-revision",
                        "commands": acquisition_commands,
                    },
                    "image_digest": image_digest,
                    "codex_cli": {
                        "version": version.stdout.strip()
                        or version.stderr.strip(),
                        "executable": str(self.codex_executable),
                    },
                    "goal_contract": {
                        "contract_id": self.goal_contract.contract_id,
                        "report_schema": self.goal_contract.report_schema,
                        "sha256": self.goal_contract.sha256,
                    },
                }
            )
            policy = CodexInteractivePolicy(
                runner=self,
                case=case,
                run_spec=run_spec,
                container_id=container_id,
                workspace=workspace,
                rounds_root=rounds_root,
                feedback_mode=self.feedback_mode,
                max_rounds=self.max_rounds,
                deadline=time.monotonic() + self.timeout,
                initial_probe=self.initial_probe,
                compact_projection=(
                    self.method_profile
                    in {"stateful-agent-v2.3", "stateful-agent-v2.4"}
                    and self.feedback_mode == "structured"
                ),
                operation_feedback=(
                    self.method_profile == "stateful-agent-v2.4"
                    and self.feedback_mode == "structured"
                ),
            )
            provider = DockerFreshEnvironmentProvider(
                source_repository=workspace,
                worktrees_root=replays_root,
                repository=case.repository,
                revision=case.revision,
                image=image_digest,
                workspace_preconditions=self.workspace_preconditions,
                create_timeout=self.container_create_timeout,
            )
            verifier_class = (
                StatefulExecutableGoalVerifierV24
                if self.method_profile == "stateful-agent-v2.4"
                else StatefulExecutableGoalVerifierV23
                if self.method_profile == "stateful-agent-v2.3"
                else StatefulExecutableGoalVerifierV22
                if self.method_profile == "stateful-agent-v2.2"
                else StatefulExecutableGoalVerifierV21
                if self.method_profile == "stateful-agent-v2.1"
                else StatefulExecutableGoalVerifierV2
                if self.method_profile == "stateful-agent-v2"
                else ExecutableGoalContractVerifier
            )
            verifier = verifier_class(
                self.goal_contract,
                observation_timeout=self.command_timeout,
                effect_auditor=lambda worktree: inspect_repository(
                    worktree,
                    case.revision,
                    required_preconditions=self.workspace_preconditions,
                ),
                **(
                    {"compact_findings": self.feedback_mode == "structured"}
                    if self.method_profile
                    in {"stateful-agent-v2.3", "stateful-agent-v2.4"}
                    else {}
                ),
            )
            result = EnvSolveEpisodeRunner(
                policy=policy,
                environment_provider=provider,
                verifier=verifier,
                candidate_validator=OpenCandidateProgramValidator(),
                budget=budget,
                max_candidates=execution_limit,
                retain_admissible_candidate=True,
                environment_strategy="fresh-candidate",
                condition=run_spec.method,
                initial_observation_summary={
                    "state_projection": self.feedback_mode,
                    "diagnostic_environment": "persistent",
                    "candidate_verification_environment": "fresh",
                    "shared_initial_goal_probe": self.initial_probe,
                    "goal_contract": {
                        "contract_id": self.goal_contract.contract_id,
                        "report_schema": self.goal_contract.report_schema,
                        "sha256": self.goal_contract.sha256,
                    },
                },
                goal_id=self.goal_contract.contract_id,
                goal_description=self.goal_contract.description,
            ).run(case, artifacts, run_spec)
            result.metadata.update(
                {
                    "core_runner": result.metadata.get("runner"),
                    "runner": "stateful-codex-cli",
                    "launcher": launcher,
                    "agent_policy": policy.metadata(),
                    "execution_budget": budget.snapshot(),
                }
            )
            write_json(artifacts.solver_result, result.to_dict())
            if artifacts.manifest.is_file():
                update_manifest(artifacts, solver=result.to_dict())
            return result
        except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
            launcher["agent_policy"] = policy.metadata() if policy is not None else None
            launcher["execution_budget"] = budget.snapshot()
            return self._setup_failure(
                artifacts,
                run_spec,
                launcher,
                f"{type(exc).__name__}: {exc}",
            )
        finally:
            if container_id:
                self._cleanup_diagnostic_container(container_id)
            cleanup_case_containers(artifacts.root)
