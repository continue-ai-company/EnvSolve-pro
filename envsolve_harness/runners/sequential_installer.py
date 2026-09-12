from __future__ import annotations

from pathlib import Path
import shlex
import time
from typing import Any, Literal

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.solver import CandidateValidation
from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.core.models import Case, RunSpec, SolverResult
from envsolve_harness.progress_replay import replay_evidence
from envsolve_harness.progress_state import (
    DeploymentCondition,
    ExecutionEvidence,
    ProjectProgressState,
    load_progress_state,
    save_progress_snapshot,
)
from envsolve_harness.runners.free_agent_census import FreeAgentCensusRunner
from envsolve_harness.runners.progress_agent import (
    ProgressAgentRunner,
    validate_progress_identity,
)
from envsolve_harness.storage.artifacts import RunArtifacts


InstallerArm = Literal["static", "adaptive"]
INSTALLER_METHODS = {
    "static": "envsolve-pro-sequential-static",
    "adaptive": "envsolve-pro-sequential-adaptive",
}


def verified_conditions(state: ProjectProgressState) -> tuple[DeploymentCondition, ...]:
    """Return distinct conditions on which the retained installer passed."""

    by_id: dict[str, DeploymentCondition] = {}
    for deployment in state.deployments:
        if deployment.evidence.status == "pass":
            by_id[deployment.condition.condition_id] = deployment.condition
    return tuple(by_id[key] for key in sorted(by_id))


def bind_default_target_python(program: str, python_version: str) -> str:
    prefix = 'export ENVSOLVE_TARGET_PYTHON="${ENVSOLVE_TARGET_PYTHON:-'
    retained = [
        line
        for line in program.splitlines()
        if not (line.startswith(prefix) and line.endswith('}"'))
    ]
    binding = f'{prefix}{python_version}}}"'
    return "\n".join((binding, *retained)).strip()


class SequentialInstallerRunner(ProgressAgentRunner):
    """Compare latest-program reuse with a regression-preserving installer."""

    runner_name = "envsolve-pro-sequential-installer-remote"
    runner_version = "1.0.0-pilot"

    def __init__(self, *, installer_arm: InstallerArm, **kwargs: Any) -> None:
        if installer_arm not in INSTALLER_METHODS:
            raise ValueError(f"unsupported installer arm: {installer_arm}")
        # R0 supplies the shared replay-first and same-capability fallback path.
        super().__init__(arm="R0", **kwargs)
        self.installer_arm = installer_arm
        self._historical_replays: list[dict[str, Any]] = []

    def _goal_contract_for_run(
        self,
        run_spec: RunSpec,
    ) -> ExecutableGoalContract | None:
        if run_spec.method != INSTALLER_METHODS[self.installer_arm]:
            return None
        return self.goal_contract

    def _validate_bootstrap(self, script: str) -> CandidateValidation:
        validation = super()._validate_bootstrap(script)
        if not validation.accepted:
            return validation
        program = validation.normalized_script or script
        return CandidateValidation(
            accepted=True,
            policy_id=validation.policy_id,
            normalized_script=bind_default_target_python(
                program,
                self.target_condition.python_version,
            ),
            details={
                **validation.details,
                "sequential_installer_input_default": (
                    self.target_condition.python_version
                ),
            },
        )

    def run(
        self,
        case: Case,
        artifacts: RunArtifacts,
        run_spec: RunSpec,
    ) -> SolverResult:
        expected = INSTALLER_METHODS[self.installer_arm]
        if run_spec.method != expected:
            return self._configuration_failure(
                artifacts,
                run_spec,
                f"expected method {expected!r}",
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

        status = self._require_preflight().get("status")
        if status in {"infrastructure_error", "unknown"}:
            return self._preflight_censor(artifacts, run_spec)
        if status == "pass":
            result = self._reuse_without_agent(artifacts, run_spec)
        else:
            result = FreeAgentCensusRunner.run(self, case, artifacts, run_spec)
        return self._finalize_progress(result, artifacts)

    def replay_program(
        self,
        case: Case,
        *,
        program: str,
        root: Path,
        condition: DeploymentCondition | None = None,
    ) -> dict[str, Any]:
        selected = condition or self.target_condition
        deployment_program = (
            "export ENVSOLVE_TARGET_PYTHON="
            + shlex.quote(selected.python_version)
            + "\n"
            + program
        )
        result = super().replay_program(
            case,
            program=deployment_program,
            root=root,
            condition=selected,
        )
        result["installer_input"] = {
            "ENVSOLVE_TARGET_PYTHON": selected.python_version,
        }
        root.mkdir(parents=True, exist_ok=True)
        write_json(root / "result.json", result)
        return result

    def _prompt(
        self,
        case: Case,
        goal_contract: ExecutableGoalContract | None = None,
    ) -> str:
        state = self._require_state()
        preflight = self._require_preflight()
        prompt = super()._prompt(case, goal_contract) + """

Every deployment supplies its requested Python version in the observable
ENVSOLVE_TARGET_PYTHON environment variable. You may branch on that input. The
same input semantics are available to both experimental arms.
"""
        if self.installer_arm == "static":
            return prompt

        conditions = [
            condition.to_dict()
            for condition in verified_conditions(state)
            if condition.condition_id != self.target_condition.condition_id
        ]
        return prompt + f"""

This arm updates one project-level adaptive installer. The only reusable learned
object is the executable bootstrap_script above. Preserve its successful behavior
on these previously verified deployment conditions while repairing the current
counterexample:
<historical_regression_conditions>
{conditions}
</historical_regression_conditions>

Use ordinary executable condition checks when behavior truly differs. Do not
encode case outcomes or verifier outputs. The candidate will be replayed in fresh
containers on the current and historical conditions before it can replace the
previous installer.
"""

    def _update_progress_state(
        self,
        result: SolverResult,
        artifacts: RunArtifacts,
    ) -> dict[str, Any]:
        if self.installer_arm == "static":
            metadata = super()._update_progress_state(result, artifacts)
            metadata["installer_arm"] = self.installer_arm
            metadata["historical_regression_wall_seconds"] = 0.0
            metadata["historical_regressions"] = []
            return metadata

        qualification = result.metadata.get("submission_qualification")
        current_qualified = not isinstance(qualification, dict) or (
            qualification.get("status") == "pass"
            and qualification.get("certified") is True
        )
        if (
            not result.generation_completed
            or not artifacts.generated_script.is_file()
            or not current_qualified
        ):
            metadata = super()._update_progress_state(result, artifacts)
            metadata["installer_arm"] = self.installer_arm
            metadata["historical_regression_wall_seconds"] = 0.0
            metadata["historical_regressions"] = []
            metadata["installer_candidate_retained"] = False
            return metadata

        state = self._require_state()
        program = artifacts.generated_script.read_text(encoding="utf-8")
        started = time.monotonic()
        replays: list[dict[str, Any]] = []
        for index, condition in enumerate(verified_conditions(state), start=1):
            if condition.condition_id == self.target_condition.condition_id:
                continue
            replay = self.replay_program(
                Case(state.case_id, state.repository, state.revision),
                program=program,
                root=(
                    artifacts.generation_dir
                    / "installer-historical-regression"
                    / f"{index:03d}-{condition.condition_id}"
                ),
                condition=condition,
            )
            replays.append(replay)
        self._historical_replays = replays
        wall = time.monotonic() - started
        failed = [item for item in replays if item.get("status") != "pass"]
        if failed:
            qualification_path = (
                artifacts.generation_dir / "submission-qualification" / "result.json"
            )
            current = (
                replay_evidence(
                    read_json(qualification_path),
                    source="postsession-target-condition-qualification",
                )
                if qualification_path.is_file()
                else ExecutionEvidence(
                    status="unknown",
                    source="agent-generation",
                    bootstrap_exit_code=None,
                    public_goal_passed=None,
                    failure_summary=result.error or "no qualification result",
                )
            )
            rejected = ExecutionEvidence(
                status="fail",
                source="historical-regression",
                bootstrap_exit_code=current.bootstrap_exit_code,
                public_goal_passed=False,
                failure_summary=(
                    f"candidate failed {len(failed)} of {len(replays)} "
                    "historical condition replays"
                ),
            )
            preflight = replay_evidence(
                self._require_preflight(),
                source="target-condition-preflight",
            )
            updated = state.record(
                condition=self.target_condition,
                program=program,
                evidence=rejected,
                trigger=preflight if preflight.status != "pass" else None,
            )
            if self.state_output_root is None:
                raise RuntimeError("state output root is not configured")
            snapshot = save_progress_snapshot(self.state_output_root, updated)
            metadata = {
                "state_output_path": str(snapshot),
                "state_output_version": updated.version,
                "state_update_wall_seconds": 0.0,
                "state_update_evidence": rejected.to_dict(),
                "installer_candidate_retained": False,
            }
        else:
            metadata = super()._update_progress_state(result, artifacts)
            metadata["installer_candidate_retained"] = True
        metadata["installer_arm"] = self.installer_arm
        metadata["historical_regression_wall_seconds"] = wall
        metadata["historical_regressions"] = [
            {
                "status": replay.get("status"),
                "target_condition": replay.get("target_condition"),
                "replay_wall_seconds": replay.get("replay_wall_seconds"),
            }
            for replay in replays
        ]
        write_json(
            artifacts.generation_dir / "installer-historical-regression.json",
            metadata["historical_regressions"],
        )
        return metadata
