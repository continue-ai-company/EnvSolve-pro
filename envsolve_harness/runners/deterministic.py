from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from envsolve_harness.core.io import write_json, write_text_atomic
from envsolve_harness.core.models import Case, RunSpec, SolverResult
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import update_manifest
from envsolve_harness.utils.provenance import sha256_file


class DeterministicScriptRunner:
    def __init__(self, source_script: Path) -> None:
        self.source_script = source_script

    def run(self, case: Case, artifacts: RunArtifacts, run_spec: RunSpec) -> SolverResult:
        started_at = datetime.now(timezone.utc).isoformat()
        write_json(artifacts.status, {"state": "generating", "updated_at": started_at})
        try:
            script = self.source_script.read_text(encoding="utf-8")
            write_text_atomic(artifacts.generated_script, script)
            result = SolverResult(
                generation_completed=True,
                method=run_spec.method,
                script_path=str(artifacts.generated_script.relative_to(artifacts.root)),
                metadata={
                    "runner": "deterministic-script",
                    "runner_version": "0.1.0",
                    "source_path": str(self.source_script.resolve()),
                    "source_sha256": sha256_file(self.source_script),
                    "started_at": started_at,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except OSError as exc:
            result = SolverResult(
                generation_completed=False,
                method=run_spec.method,
                error=f"{type(exc).__name__}: {exc}",
                metadata={
                    "runner": "deterministic-script",
                    "runner_version": "0.1.0",
                    "source_path": str(self.source_script.resolve()),
                    "started_at": started_at,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        write_json(artifacts.solver_result, result.to_dict())
        write_text_atomic(artifacts.solver_log, result.error or "Generation completed successfully.\n")
        update_manifest(artifacts, solver=result.to_dict())
        write_json(
            artifacts.status,
            {
                "state": "generated" if result.generation_completed else "failed",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return result
