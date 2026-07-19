from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil

from envsolve_harness.audit import audit_run
from envsolve_harness.core.io import read_json, read_jsonl, write_json, write_text_atomic
from envsolve_harness.core.models import Case, RunSpec, SolverResult
from envsolve_harness.scripts.envbench_trajectory import (
    aggregate_token_usage,
    commands_from_trajectory,
    distill_envbench_commands,
)
from envsolve_harness.scripts.replay_actions import REPLAY_IR_POLICY
from envsolve_harness.storage.artifacts import RunArtifacts, safe_name
from envsolve_harness.storage.manifest import update_manifest
from envsolve_harness.utils.provenance import sha256_file


class RecordedEnvBenchTrajectoryRunner:
    def __init__(self, source_run_root: Path) -> None:
        self.source_run_root = source_run_root

    def _finish(self, artifacts: RunArtifacts, result: SolverResult, log: str) -> SolverResult:
        write_json(artifacts.solver_result, result.to_dict())
        write_text_atomic(artifacts.solver_log, log)
        update_manifest(artifacts, solver=result.to_dict())
        write_json(
            artifacts.status,
            {
                "state": "generated" if result.generation_completed else "failed",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return result

    def run(self, case: Case, artifacts: RunArtifacts, run_spec: RunSpec) -> SolverResult:
        started_at = datetime.now(timezone.utc).isoformat()
        write_json(artifacts.status, {"state": "generating", "updated_at": started_at})
        source_root = self.source_run_root / safe_name(case.case_id)
        metadata = {
            "runner": "recorded-envbench-trajectory",
            "runner_version": "0.2.0",
            "audit_requirements": {"repository_integrity": True},
            "source_run_root": str(self.source_run_root.resolve()),
            "source_case_root": str(source_root.resolve()),
            "started_at": started_at,
        }
        try:
            manifest = read_json(source_root / "manifest.json")
            source_solver = manifest["solver"]
            source_run = manifest["run"]
            source_case = manifest["case"]
            trajectory_value = source_solver.get("trajectory_path")
            trajectory_relative = (
                Path(trajectory_value)
                if trajectory_value
                else Path("generation/trajectory.jsonl")
            )
            trajectory_source = source_root / trajectory_relative
        except (OSError, KeyError, TypeError, ValueError) as exc:
            error = f"Unable to load recorded trajectory: {type(exc).__name__}: {exc}"
            return self._finish(
                artifacts, SolverResult(False, run_spec.method, error=error, metadata=metadata), error + "\n"
            )

        source_metadata = source_solver.get("metadata") or {}
        source_integrity = source_metadata.get("repository_integrity") or {}
        source_error = str(source_solver.get("error") or "")
        source_runner = source_metadata.get("runner")
        distillation_only_failure = (
            source_solver.get("generation_completed") is False
            and source_metadata.get("process_exit_code") == 0
            and source_error.startswith(
                (
                    "EnvBench trajectory contains unsupported commands:",
                    "trajectory contains unsupported commands:",
                )
            )
            and (
                source_runner != "envsolve-v0"
                or (source_metadata.get("v0_completion") or {}).get("passed") is True
            )
        )
        source_audit = audit_run(source_root)
        identity_valid = (
            source_case == case.to_dict()
            and source_run.get("model") == run_spec.model
            and (
                source_solver.get("generation_completed") is True
                or distillation_only_failure
            )
            and source_metadata.get("checked_out_revision") == case.revision
            and source_integrity.get("valid") is True
            and source_audit.valid
            and not trajectory_relative.is_absolute()
            and trajectory_source.resolve().is_relative_to(source_root.resolve())
            and trajectory_source.is_file()
        )
        metadata["source_identity_valid"] = identity_valid
        metadata["source_audit_valid"] = source_audit.valid
        metadata["source_distillation_only_failure"] = distillation_only_failure
        metadata["repository_integrity"] = source_integrity
        if not identity_valid:
            error = "Recorded EnvBench trajectory failed identity or integrity validation"
            return self._finish(
                artifacts, SolverResult(False, run_spec.method, error=error, metadata=metadata), error + "\n"
            )

        shutil.copyfile(trajectory_source, artifacts.trajectory_jsonl)
        try:
            records = read_jsonl(artifacts.trajectory_jsonl)
            distilled = distill_envbench_commands(
                commands_from_trajectory(records),
                project_directory=f"{case.repository.replace('/', '__')}@{case.revision}",
            )
        except (OSError, TypeError, ValueError) as exc:
            error = f"Invalid recorded trajectory: {type(exc).__name__}: {exc}"
            return self._finish(
                artifacts, SolverResult(False, run_spec.method, error=error, metadata=metadata), error + "\n"
            )

        metadata.update(
            {
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "source_trajectory_sha256": sha256_file(trajectory_source),
                "token_usage": aggregate_token_usage(records),
                "source_solver_metadata": source_metadata,
                "distillation": {
                    "policy": f"envbench-{REPLAY_IR_POLICY}",
                    "kept_count": len(distilled.kept_commands),
                    "dropped_count": len(distilled.dropped_commands),
                    "action_count": len(distilled.actions),
                    "actions": [action.to_dict() for action in distilled.actions],
                    "unsupported_count": len(distilled.unknown_commands),
                    "unsupported_commands": list(distilled.unknown_commands),
                    "unknown_count": len(distilled.unknown_commands),
                    "unknown_commands": list(distilled.unknown_commands),
                },
            }
        )
        if distilled.unknown_commands:
            error = (
                "Recorded EnvBench trajectory contains unsupported commands: "
                f"{list(distilled.unknown_commands)}"
            )
            return self._finish(
                artifacts, SolverResult(False, run_spec.method, error=error, metadata=metadata), error + "\n"
            )
        if not distilled.kept_commands:
            error = "Recorded EnvBench trajectory contains no replayable environment changes"
            return self._finish(
                artifacts, SolverResult(False, run_spec.method, error=error, metadata=metadata), error + "\n"
            )

        write_text_atomic(artifacts.generated_script, distilled.script)
        result = SolverResult(
            True,
            run_spec.method,
            script_path=str(artifacts.generated_script.relative_to(artifacts.root)),
            trajectory_path=str(artifacts.trajectory_jsonl.relative_to(artifacts.root)),
            metadata=metadata,
        )
        return self._finish(artifacts, result, "Re-distilled a validated recorded EnvBench trajectory.\n")
