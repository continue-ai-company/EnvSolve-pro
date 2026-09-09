from __future__ import annotations

from pathlib import Path
import time
from typing import Any, Literal

from envsolve.runtime.docker import DockerFreshEnvironmentProvider
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.boundary_v6 import BoundaryV6OpenCandidateProgramValidator
from envsolve_harness.codex.minimal_b_mcp import CleanReplayService
from envsolve_harness.core.io import (
    read_json,
    read_jsonl,
    write_json,
    write_text_atomic,
)
from envsolve_harness.core.models import Case, RunSpec, SolverResult
from envsolve_harness.execution.remote_docker import (
    RemoteDockerCommandAdapter,
    RemoteExactRevisionSourceCache,
)
from envsolve_harness.integrity.repository import inspect_repository
from envsolve_harness.progress_replay import (
    PythonConditionVerifier,
    compact_replay_feedback,
    replay_evidence,
)
from envsolve_harness.progress_state import (
    DeploymentCondition,
    ExecutionEvidence,
    ProjectProgressState,
    load_progress_state,
    save_progress_snapshot,
)
from envsolve_harness.runners.free_agent_census import FreeAgentCensusRunner
from envsolve_harness.storage.artifacts import RunArtifacts


ProgressArm = Literal["R0", "R1", "P"]
PROGRESS_METHODS = {
    "R0": "envsolve-pro-progress-r0",
    "R1": "envsolve-pro-progress-r1",
    "P": "envsolve-pro-progress-p",
}


def validate_progress_identity(state: ProjectProgressState, case: Case) -> None:
    expected = (case.case_id, case.repository, case.revision)
    observed = (state.case_id, state.repository, state.revision)
    if observed != expected:
        raise ValueError(
            "progress state identity does not match the requested case: "
            f"expected={expected!r}, observed={observed!r}"
        )


def fork_codex_command(command: list[str], session_id: str) -> list[str]:
    session_id = session_id.strip()
    if not session_id:
        raise ValueError("R1 requires a source Codex session ID")
    if len(command) < 3 or command[1] != "exec" or command[-1:] != ["-"]:
        raise ValueError("unexpected Codex exec command shape")

    forked = list(command)
    forked.insert(2, "fork")
    for option in ("--sandbox", "--cd"):
        if option not in forked:
            raise ValueError(f"Codex exec command is missing {option}")
        index = forked.index(option)
        del forked[index : index + 2]
    forked[-1:] = [
        "--config",
        'sandbox_mode="read-only"',
        session_id,
        "-",
    ]
    return forked


def progress_session_id(records: list[dict[str, Any]]) -> str | None:
    for record in records:
        if record.get("type") != "thread.started":
            continue
        value = record.get("thread_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


class ProgressAgentRunner(FreeAgentCensusRunner):
    """Compare artifact reuse, full Agent history, and minimal explicit state."""

    runner_name = "envsolve-pro-project-progress-remote"
    runner_version = "1.0.0-pilot"

    def __init__(
        self,
        *,
        arm: ProgressArm,
        state_path: Path,
        target_condition: DeploymentCondition,
        source_session_id: str | None = None,
        update_state: bool = False,
        state_output_root: Path | None = None,
        **kwargs: Any,
    ) -> None:
        if arm not in PROGRESS_METHODS:
            raise ValueError(f"unsupported progress arm: {arm}")
        if arm == "R1" and not (source_session_id or "").strip():
            raise ValueError("R1 requires a source Codex session ID")
        if update_state and state_output_root is None:
            raise ValueError("state updates require an output root")
        super().__init__(**kwargs)
        self.arm = arm
        self.state_path = state_path.resolve()
        self.target_condition = target_condition
        self.source_session_id = (
            source_session_id.strip() if source_session_id is not None else None
        )
        self.update_state = update_state
        self.state_output_root = (
            state_output_root.resolve() if state_output_root is not None else None
        )
        self._progress_state: ProjectProgressState | None = None
        self._preflight: dict[str, Any] | None = None

    def _goal_contract_for_run(
        self,
        run_spec: RunSpec,
    ) -> ExecutableGoalContract | None:
        expected = PROGRESS_METHODS[self.arm]
        if run_spec.method != expected:
            return None
        return self.goal_contract

    def _submission_verifier(
        self,
        *,
        case: Case,
        artifacts: RunArtifacts,
        adapter: RemoteDockerCommandAdapter,
    ) -> PythonConditionVerifier:
        del artifacts
        if self.goal_contract is None:
            raise ValueError("progress replay requires a public goal contract")
        return PythonConditionVerifier(
            self.goal_contract,
            required_python=self.target_condition.python_version,
            observation_timeout=self.command_timeout,
            effect_auditor=lambda worktree: inspect_repository(
                worktree,
                case.revision,
                required_preconditions=self.workspace_preconditions,
            ),
            run_command=adapter,
        )

    def _preflight_program(
        self,
        case: Case,
        artifacts: RunArtifacts,
        state: ProjectProgressState,
    ) -> dict[str, Any]:
        if self.goal_contract is None:
            raise ValueError("progress preflight requires a public goal contract")
        root = artifacts.generation_dir / "progress-preflight"
        source = root / "source"
        acquisition = RemoteExactRevisionSourceCache(
            self.transport,
            self.git_fetch_timeout,
        ).acquire(
            repository=case.repository,
            revision=case.revision,
            destination=source,
        )
        image_digest = self._image_digest()
        adapter = RemoteDockerCommandAdapter(
            self.transport,
            sync_timeout=max(self.command_timeout, self.git_fetch_timeout),
            expose_gpus=self.expose_gpus,
        )
        provider = DockerFreshEnvironmentProvider(
            source_repository=source,
            worktrees_root=root / "worktrees",
            repository=case.repository,
            revision=case.revision,
            image=image_digest,
            workspace_preconditions=self.workspace_preconditions,
            create_timeout=self.container_create_timeout,
            run_command=adapter,
        )
        verifier = self._submission_verifier(
            case=case,
            artifacts=artifacts,
            adapter=adapter,
        )
        service = CleanReplayService(
            provider=provider,
            verifier=verifier,
            repository=case.repository,
            revision=case.revision,
            image_digest=image_digest,
            goal_contract_sha256=self.goal_contract.sha256,
            trace_path=root / "replays.jsonl",
            certification_path=root / "certification.json",
            programs_root=root / "programs",
        )
        service.validator = BoundaryV6OpenCandidateProgramValidator()
        started = time.monotonic()
        result = service.submit(state.current_program)
        result["preflight_wall_seconds"] = time.monotonic() - started
        result["repository_acquisition"] = acquisition
        result["target_condition"] = self.target_condition.to_dict()
        write_json(root / "result.json", result)
        return result

    def _prompt(
        self,
        case: Case,
        goal_contract: ExecutableGoalContract | None = None,
    ) -> str:
        state = self._require_state()
        preflight = self._require_preflight()
        feedback = compact_replay_feedback(preflight)
        target = self.target_condition.to_dict()
        if self.arm == "R1":
            return f"""\
Continue the completed deployment session for the same exact project revision.
You now have a new construction container and the same deployment tools. Improve
the previous bootstrap program for this predeclared target condition:
{target}

Its previous program was replayed once in a fresh target container before this
turn. Here is the same bounded execution evidence available to every repair arm:
<preflight_feedback>
{feedback}
</preflight_feedback>

Use the full prior conversation and ordinary execution feedback to diagnose and
repair the program. Preserve any behavior that already works. Return the required
JSON object with a self-contained bootstrap_script; do not stop at an explanation.
"""

        prompt = super()._prompt(case, goal_contract)
        if self.arm == "P":
            context = state.compact_context(self.target_condition)
            reusable = f"""\
Use this minimal evidence-backed project solving state as reusable progress:
<project_progress_state>
{context}
</project_progress_state>
"""
        else:
            reusable = f"""\
An ordinary previously successful bootstrap artifact is available below. No
other project-specific state or prior conversation is provided:
<previous_bootstrap_script>
{state.current_program}
</previous_bootstrap_script>
"""
        return (
            prompt
            + "\n"
            + reusable
            + f"""\

The old program was replayed once in a fresh target container. Repair the program
using this bounded execution feedback:
<preflight_feedback>
{feedback}
</preflight_feedback>

Target condition: {target}
Preserve working steps and change only what the target condition or observed
failure requires. Return a complete self-contained bootstrap_script.
"""
        )

    def _codex_command(self, **kwargs: Any) -> list[str]:
        command = super()._codex_command(**kwargs)
        if self.arm != "R1":
            return command
        return fork_codex_command(command, self.source_session_id or "")

    def _augment_generation_metadata(
        self,
        artifacts: RunArtifacts,
        metadata: dict[str, Any],
    ) -> None:
        super()._augment_generation_metadata(artifacts, metadata)
        metadata["project_progress"] = self._progress_metadata(artifacts)

    def run(
        self,
        case: Case,
        artifacts: RunArtifacts,
        run_spec: RunSpec,
    ) -> SolverResult:
        if run_spec.method != PROGRESS_METHODS[self.arm]:
            return self._configuration_failure(
                artifacts,
                run_spec,
                f"expected method {PROGRESS_METHODS[self.arm]!r}",
            )
        try:
            state = load_progress_state(self.state_path)
            validate_progress_identity(state, case)
            self._progress_state = state
            self._preflight = self._preflight_program(case, artifacts, state)
        except (OSError, RuntimeError, ValueError) as exc:
            return self._configuration_failure(
                artifacts,
                run_spec,
                f"preflight failed: {type(exc).__name__}: {exc}",
            )

        status = self._preflight.get("status")
        if status in {"infrastructure_error", "unknown"}:
            return self._preflight_censor(artifacts, run_spec)
        if status == "pass" and self.arm in {"R0", "P"}:
            result = self._reuse_without_agent(artifacts, run_spec)
        else:
            result = super().run(case, artifacts, run_spec)
        return self._finalize_progress(result, artifacts)

    def _reuse_without_agent(
        self,
        artifacts: RunArtifacts,
        run_spec: RunSpec,
    ) -> SolverResult:
        state = self._require_state()
        write_text_atomic(artifacts.generated_script, state.current_program + "\n")
        result = SolverResult(
            True,
            run_spec.method,
            script_path=str(artifacts.generated_script.relative_to(artifacts.root)),
            trajectory_path="generation/progress-preflight/replays.jsonl",
            metadata={
                "runner": self.runner_name,
                "runner_version": self.runner_version,
                "official_evaluator_access": "post-episode-only",
                "token_usage": {
                    "input_tokens": 0,
                    "cached_input_tokens": 0,
                    "output_tokens": 0,
                },
                "model_invoked": False,
                "project_progress": self._progress_metadata(artifacts),
                "finished_at": self._now(),
            },
        )
        return self._finish(
            artifacts,
            result,
            "Existing program passed the fresh target-condition preflight; "
            "no model was invoked.\n",
        )

    def _preflight_censor(
        self,
        artifacts: RunArtifacts,
        run_spec: RunSpec,
    ) -> SolverResult:
        status = self._require_preflight().get("status")
        result = SolverResult(
            False,
            run_spec.method,
            trajectory_path="generation/progress-preflight/replays.jsonl",
            error=f"Preflight {status}; censored without Agent repair",
            metadata={
                "runner": self.runner_name,
                "runner_version": self.runner_version,
                "official_evaluator_access": "post-episode-only",
                "model_invoked": False,
                "project_progress": self._progress_metadata(artifacts),
                "finished_at": self._now(),
            },
        )
        return self._finish(artifacts, result, result.error + "\n")

    def _configuration_failure(
        self,
        artifacts: RunArtifacts,
        run_spec: RunSpec,
        error: str,
    ) -> SolverResult:
        result = SolverResult(
            False,
            run_spec.method,
            error=error,
            metadata={
                "runner": self.runner_name,
                "runner_version": self.runner_version,
                "official_evaluator_access": "post-episode-only",
                "finished_at": self._now(),
            },
        )
        return self._finish(artifacts, result, error + "\n")

    def _finalize_progress(
        self,
        result: SolverResult,
        artifacts: RunArtifacts,
    ) -> SolverResult:
        metadata = dict(result.metadata)
        progress = self._progress_metadata(artifacts)
        progress["model_invoked"] = bool(
            metadata.get("process_exit_code") is not None
        )
        if self.arm == "R1" and artifacts.trajectory_jsonl.is_file():
            records = read_jsonl(artifacts.trajectory_jsonl)
            progress["result_session_id"] = progress_session_id(records)
        if self.update_state:
            progress.update(self._update_progress_state(result, artifacts))
        metadata["project_progress"] = progress
        finalized = SolverResult(
            result.generation_completed,
            result.method,
            script_path=result.script_path,
            trajectory_path=result.trajectory_path,
            error=result.error,
            metadata=metadata,
        )
        previous_log = (
            artifacts.solver_log.read_text(encoding="utf-8")
            if artifacts.solver_log.is_file()
            else ""
        )
        return self._finish(artifacts, finalized, previous_log)

    def _update_progress_state(
        self,
        result: SolverResult,
        artifacts: RunArtifacts,
    ) -> dict[str, Any]:
        state = self._require_state()
        preflight_evidence = replay_evidence(
            self._require_preflight(),
            source="target-condition-preflight",
        )
        qualification_path = (
            artifacts.generation_dir / "submission-qualification" / "result.json"
        )
        if qualification_path.is_file():
            evidence = replay_evidence(
                read_json(qualification_path),
                source="postsession-target-condition-qualification",
            )
        elif (
            preflight_evidence.status == "pass"
            and result.metadata.get("process_exit_code") is None
        ):
            evidence = preflight_evidence
        else:
            evidence = ExecutionEvidence(
                status="unknown",
                source="agent-generation",
                bootstrap_exit_code=None,
                public_goal_passed=None,
                failure_summary=result.error or "no qualification result",
            )
        program = (
            artifacts.generated_script.read_text(encoding="utf-8")
            if artifacts.generated_script.is_file()
            else state.current_program
        )
        trigger = preflight_evidence if preflight_evidence.status != "pass" else None
        started = time.monotonic()
        updated = state.record(
            condition=self.target_condition,
            program=program,
            evidence=evidence,
            trigger=trigger,
        )
        if self.state_output_root is None:
            raise RuntimeError("state output root is not configured")
        snapshot = save_progress_snapshot(self.state_output_root, updated)
        return {
            "state_output_path": str(snapshot),
            "state_output_version": updated.version,
            "state_update_wall_seconds": time.monotonic() - started,
            "state_update_evidence": evidence.to_dict(),
        }

    def _progress_metadata(self, artifacts: RunArtifacts) -> dict[str, Any]:
        state = self._require_state()
        preflight = self._require_preflight()
        return {
            "arm": self.arm,
            "state_input_path": str(self.state_path),
            "state_input_version": state.version,
            "target_condition": self.target_condition.to_dict(),
            "preflight_result_path": str(
                (artifacts.generation_dir / "progress-preflight" / "result.json")
                .relative_to(artifacts.root)
            ),
            "preflight_status": preflight.get("status"),
            "preflight_wall_seconds": preflight.get("preflight_wall_seconds"),
            "source_session_id": self.source_session_id,
            "state_update_enabled": self.update_state,
        }

    def _require_state(self) -> ProjectProgressState:
        if self._progress_state is None:
            raise RuntimeError("project progress state has not been loaded")
        return self._progress_state

    def _require_preflight(self) -> dict[str, Any]:
        if self._preflight is None:
            raise RuntimeError("project progress preflight has not run")
        return self._preflight
