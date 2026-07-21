from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil

from envsolve_harness.audit import audit_run
from envsolve_harness.core.io import read_json, read_jsonl, write_json, write_text_atomic
from envsolve_harness.core.models import Case, RunSpec, SolverResult
from envsolve_harness.integrity.repository import inspect_repository
from envsolve_harness.runners.codex_cli import audit_script_grounding
from envsolve_harness.storage.artifacts import RunArtifacts, safe_name
from envsolve_harness.storage.manifest import update_manifest
from envsolve_harness.utils.provenance import sha256_file


class RecordedCodexCliRunner:
    """Re-finalize a completed Codex episode after wrapper-only policy fixes."""

    def __init__(self, source_run_root: Path) -> None:
        self.source_run_root = source_run_root

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _finish(
        self,
        artifacts: RunArtifacts,
        result: SolverResult,
        log: str,
    ) -> SolverResult:
        write_json(artifacts.solver_result, result.to_dict())
        write_text_atomic(artifacts.solver_log, log)
        update_manifest(artifacts, solver=result.to_dict())
        write_json(
            artifacts.status,
            {
                "state": "generated" if result.generation_completed else "failed",
                "updated_at": self._now(),
            },
        )
        return result

    def run(self, case: Case, artifacts: RunArtifacts, run_spec: RunSpec) -> SolverResult:
        started_at = self._now()
        write_json(artifacts.status, {"state": "generating", "updated_at": started_at})
        source_root = self.source_run_root / safe_name(case.case_id)
        metadata = {
            "runner": "recorded-codex-cli",
            "runner_version": "0.1.0",
            "audit_requirements": {"repository_integrity": True},
            "source_run_root": str(self.source_run_root.resolve()),
            "source_case_root": str(source_root.resolve()),
            "model_reexecuted": False,
            "official_evaluator_access": "post-refinalization-only",
            "started_at": started_at,
        }
        try:
            manifest = read_json(source_root / "manifest.json")
            source_solver = manifest["solver"]
            source_metadata = source_solver["metadata"]
            source_case = manifest["case"]
            source_run = manifest["run"]
            workspace = source_root / "generation/workspace"
            events = source_root / "generation/trajectory.jsonl"
            trace = source_root / "generation/container-commands.jsonl"
            output = source_root / "generation/codex-control/final-output.json"
            submission = read_json(output)
            command_records = read_jsonl(trace)
            source_audit = audit_run(source_root)
            integrity = inspect_repository(workspace, case.revision)
        except (OSError, KeyError, TypeError, ValueError) as exc:
            error = f"Unable to load recorded Codex episode: {type(exc).__name__}: {exc}"
            return self._finish(
                artifacts,
                SolverResult(False, run_spec.method, error=error, metadata=metadata),
                error + "\n",
            )

        successful_commands = [
            record
            for record in command_records
            if record.get("exit_code") == 0
            and not record.get("timed_out")
            and not record.get("infrastructure_error")
        ]
        source_failure_is_refinalizable = (
            source_solver.get("generation_completed") is False
            and str(source_solver.get("error") or "").startswith(
                "RuntimeError: Codex CLI repository integrity failed:"
            )
            and source_metadata.get("runner") == "codex-cli"
            and source_metadata.get("process_exit_code") == 0
        )
        identity_valid = (
            source_case == case.to_dict()
            and source_run.get("model") == run_spec.model
            and source_failure_is_refinalizable
            and source_metadata.get("checked_out_revision") == case.revision
            and source_audit.valid
            and integrity.valid
            and events.is_file()
            and trace.is_file()
            and output.is_file()
            and bool(successful_commands)
            and isinstance(submission, dict)
            and isinstance(submission.get("bootstrap_script"), str)
            and bool(submission["bootstrap_script"].strip())
        )
        metadata.update(
            {
                "source_identity_valid": identity_valid,
                "source_audit_valid": source_audit.valid,
                "source_failure_is_refinalizable": source_failure_is_refinalizable,
                "source_solver_error": source_solver.get("error"),
                "repository_integrity": integrity.to_dict(),
                "checked_out_revision": integrity.checked_out_revision,
            }
        )
        if not identity_valid:
            error = "Recorded Codex episode failed identity, completion, or integrity validation"
            return self._finish(
                artifacts,
                SolverResult(False, run_spec.method, error=error, metadata=metadata),
                error + "\n",
            )

        shutil.copyfile(events, artifacts.trajectory_jsonl)
        copied_trace = artifacts.generation_dir / "container-commands.jsonl"
        shutil.copyfile(trace, copied_trace)
        copied_output = artifacts.generation_dir / "codex-final-output.json"
        shutil.copyfile(output, copied_output)
        script = submission["bootstrap_script"].strip() + "\n"
        write_text_atomic(artifacts.generated_script, script)
        metadata.update(
            {
                "finished_at": self._now(),
                "source_artifacts": {
                    "events_sha256": sha256_file(events),
                    "container_commands_sha256": sha256_file(trace),
                    "final_output_sha256": sha256_file(output),
                },
                "container_command_trace": {
                    "path": str(copied_trace.relative_to(artifacts.root)),
                    "count": len(command_records),
                    "successful_count": len(successful_commands),
                },
                "token_usage": source_metadata.get("token_usage", {}),
                "submission": {
                    "summary": str(submission.get("summary", "")),
                    "script_grounding": audit_script_grounding(script, command_records),
                    "output_path": str(copied_output.relative_to(artifacts.root)),
                },
            }
        )
        result = SolverResult(
            True,
            run_spec.method,
            script_path=str(artifacts.generated_script.relative_to(artifacts.root)),
            trajectory_path=str(artifacts.trajectory_jsonl.relative_to(artifacts.root)),
            metadata=metadata,
        )
        return self._finish(
            artifacts,
            result,
            "Re-finalized a validated recorded Codex episode without model reexecution.\n",
        )
