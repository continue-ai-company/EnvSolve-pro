from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

from envsolve_harness.core.io import read_json, write_json, write_text_atomic
from envsolve_harness.core.models import Case, ModelPricing, RunSpec, SolverResult
from envsolve_harness.integrity.repository import inspect_repository
from envsolve_harness.scripts.repo2run import (
    compile_repo2run_open_program,
    distill_repo2run_commands,
)
from envsolve_harness.scripts.replay_actions import REPLAY_IR_POLICY
from envsolve_harness.scripts.open_program import OPEN_PROGRAM_POLICY
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import update_manifest
from envsolve_harness.utils.provenance import git_provenance, sha256_file


class Repo2RunRunner:
    def __init__(
        self,
        repo2run_root: Path,
        timeout: int = 7200,
        model_request_timeout: int = 180,
        model_max_retries: int = 2,
        max_model_requests: int = 30,
        max_total_tokens: int = 1_000_000,
        max_estimated_cost_usd: float = 5.0,
        pricing: ModelPricing | None = None,
        harness_root: Path | None = None,
        candidate_interface: str = "typed-replay",
    ) -> None:
        self.repo2run_root = repo2run_root
        self.timeout = timeout
        self.model_request_timeout = model_request_timeout
        self.model_max_retries = model_max_retries
        self.max_model_requests = max_model_requests
        self.max_total_tokens = max_total_tokens
        self.max_estimated_cost_usd = max_estimated_cost_usd
        self.pricing = pricing
        self.harness_root = harness_root or Path(__file__).resolve().parents[2]
        if candidate_interface not in {"typed-replay", "open-program"}:
            raise ValueError("Unknown Repo2Run candidate interface")
        self.candidate_interface = candidate_interface

    def _finish(self, artifacts: RunArtifacts, result: SolverResult, log: str) -> SolverResult:
        if artifacts.budget_ledger.is_file():
            ledger = read_json(artifacts.budget_ledger)
            result.metadata["online_budget"] = ledger
            if ledger.get("termination") and "termination" not in result.metadata:
                result.metadata["termination"] = ledger["termination"]
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

    def _prepare_output_root(self, repository: str) -> tuple[Path, bool]:
        output_base = (self.repo2run_root / "output").resolve()
        output_root = (output_base / repository).resolve()
        if output_base not in output_root.parents:
            raise ValueError("Repo2Run repository escaped the output root")
        existed = output_root.exists()
        if existed:
            shutil.rmtree(output_root)
        return output_root, existed

    def run(self, case: Case, artifacts: RunArtifacts, run_spec: RunSpec) -> SolverResult:
        started_at = datetime.now(timezone.utc).isoformat()
        write_json(artifacts.status, {"state": "generating", "updated_at": started_at})
        budget_bridge_path = self.repo2run_root / "build_agent/utils/llm_client.py"
        budget_bridge = {
            "path": "build_agent/utils/llm_client.py",
            "exists": budget_bridge_path.is_file(),
        }
        if budget_bridge_path.is_file():
            budget_bridge["sha256"] = sha256_file(budget_bridge_path)
        base_metadata = {
            "runner": "repo2run",
            "runner_version": "0.3.0",
            "candidate_interface": self.candidate_interface,
            "audit_requirements": {
                "repository_integrity": True,
                "online_budget": True,
            },
            "repo2run": git_provenance(self.repo2run_root),
            "budget_bridge": budget_bridge,
            "timeout": self.timeout,
            "resource_budget": {
                "generation_wall_clock_seconds": self.timeout,
                "model_request_timeout_seconds": self.model_request_timeout,
                "model_max_retries": self.model_max_retries,
                "model_max_requests": self.max_model_requests,
                "model_max_total_tokens": self.max_total_tokens,
                "model_max_estimated_cost_usd": self.max_estimated_cost_usd,
            },
            "started_at": started_at,
            "credential_environment": {
                "OPENAI_API_KEY": bool(os.environ.get("OPENAI_API_KEY")),
                "OPENAI_BASE_URL": bool(os.environ.get("OPENAI_BASE_URL")),
            },
        }
        if not run_spec.model:
            return self._finish(
                artifacts,
                SolverResult(False, run_spec.method, error="Repo2Run requires RunSpec.model", metadata=base_metadata),
                "Repo2Run requires a model identifier.\n",
            )
        if not os.environ.get("OPENAI_API_KEY"):
            return self._finish(
                artifacts,
                SolverResult(False, run_spec.method, error="OPENAI_API_KEY is not set", metadata=base_metadata),
                "OPENAI_API_KEY is not set. The key value is never recorded.\n",
            )
        if not budget_bridge_path.is_file():
            return self._finish(
                artifacts,
                SolverResult(
                    False,
                    run_spec.method,
                    error="Repo2Run online budget bridge is missing",
                    metadata=base_metadata,
                ),
                "Repo2Run online budget bridge is required before making a provider request.\n",
            )
        if self.pricing is None or self.pricing.model != run_spec.model:
            return self._finish(
                artifacts,
                SolverResult(
                    False,
                    run_spec.method,
                    error=f"Frozen model pricing is not configured for {run_spec.model!r}",
                    metadata=base_metadata,
                ),
                "Frozen model pricing is required before making a provider request.\n",
            )
        base_metadata["resource_budget"]["model_pricing"] = {
            "model": self.pricing.model,
            "input_cost_per_million": self.pricing.input_cost_per_million,
            "output_cost_per_million": self.pricing.output_cost_per_million,
            "cache_read_cost_per_million": self.pricing.cache_read_cost_per_million,
            "source_url": self.pricing.source_url,
            "snapshot_date": self.pricing.snapshot_date,
        }

        try:
            output_root, removed_prior_output = self._prepare_output_root(
                case.repository
            )
        except (OSError, ValueError) as exc:
            return self._finish(
                artifacts,
                SolverResult(
                    False,
                    run_spec.method,
                    error=f"Repo2Run output isolation failed: {type(exc).__name__}: {exc}",
                    metadata=base_metadata,
                ),
                f"Repo2Run output isolation failed: {type(exc).__name__}: {exc}\n",
            )
        base_metadata["output_isolation"] = {
            "policy": "fresh-per-case-output-v1",
            "removed_prior_output": removed_prior_output,
            "relative_path": f"output/{case.repository}",
        }

        command = [
            str(self.repo2run_root / ".venv/bin/python"),
            "main.py",
            "--full_name", case.repository,
            "--sha", case.revision,
            "--root_path", str(self.repo2run_root),
            "--llm", run_spec.model,
        ]
        process_env = os.environ.copy()
        python_path = process_env.get("PYTHONPATH")
        process_env["PYTHONPATH"] = (
            f"{self.harness_root}{os.pathsep}{python_path}" if python_path else str(self.harness_root)
        )
        budget_environment = {
            "ENVSOLVE_BUDGET_LEDGER_PATH": str(artifacts.budget_ledger),
            "ENVSOLVE_BUDGET_MAX_MODEL_REQUESTS": str(self.max_model_requests),
            "ENVSOLVE_BUDGET_MAX_TOTAL_TOKENS": str(self.max_total_tokens),
            "ENVSOLVE_BUDGET_MAX_ESTIMATED_COST_USD": str(self.max_estimated_cost_usd),
            "ENVSOLVE_BUDGET_MODEL": self.pricing.model,
            "ENVSOLVE_BUDGET_INPUT_COST_PER_MILLION": str(
                self.pricing.input_cost_per_million
            ),
            "ENVSOLVE_BUDGET_OUTPUT_COST_PER_MILLION": str(
                self.pricing.output_cost_per_million
            ),
            "ENVSOLVE_MODEL_REQUEST_TIMEOUT": str(self.model_request_timeout),
            "ENVSOLVE_MODEL_MAX_RETRIES": str(self.model_max_retries),
        }
        if self.pricing.cache_read_cost_per_million is not None:
            budget_environment["ENVSOLVE_BUDGET_CACHE_READ_COST_PER_MILLION"] = str(
                self.pricing.cache_read_cost_per_million
            )
        if self.pricing.source_url:
            budget_environment["ENVSOLVE_BUDGET_PRICING_SOURCE_URL"] = self.pricing.source_url
        if self.pricing.snapshot_date:
            budget_environment["ENVSOLVE_BUDGET_PRICING_SNAPSHOT_DATE"] = (
                self.pricing.snapshot_date
            )
        process_env.update(budget_environment)
        try:
            process = subprocess.run(
                command,
                cwd=self.repo2run_root / "build_agent",
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout,
                env=process_env,
            )
            log = f"$ {' '.join(command)}\n\n[stdout]\n{process.stdout}\n[stderr]\n{process.stderr}"
        except (OSError, subprocess.TimeoutExpired) as exc:
            metadata = {**base_metadata, "finished_at": datetime.now(timezone.utc).isoformat()}
            return self._finish(
                artifacts,
                SolverResult(False, run_spec.method, error=f"{type(exc).__name__}: {exc}", metadata=metadata),
                f"{type(exc).__name__}: {exc}\n",
            )

        commands_path = output_root / "inner_commands.json"
        repo_path = self.repo2run_root / "utils/repo" / case.repository / "repo"
        metadata = {
            **base_metadata,
            "command": command,
            "process_exit_code": process.returncode,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        if process.returncode != 0 or not commands_path.is_file():
            error = f"Repo2Run exited with {process.returncode}; inner_commands.json exists={commands_path.is_file()}"
            return self._finish(
                artifacts, SolverResult(False, run_spec.method, error=error, metadata=metadata), log
            )

        integrity = inspect_repository(repo_path, case.revision)
        metadata["repository_integrity"] = integrity.to_dict()
        metadata["checked_out_revision"] = integrity.checked_out_revision
        metadata["changed_source_files"] = [
            path
            for path in integrity.tracked_changes
            if Path(path).suffix in {".c", ".cpp", ".py", ".pyi", ".so"}
        ]
        if not integrity.valid:
            error = f"Repo2Run repository integrity failed: {integrity.to_dict()['violations']}"
            return self._finish(
                artifacts, SolverResult(False, run_spec.method, error=error, metadata=metadata), log
            )

        records = json.loads(commands_path.read_text(encoding="utf-8"))
        distilled = (
            compile_repo2run_open_program(records)
            if self.candidate_interface == "open-program"
            else distill_repo2run_commands(records)
        )
        metadata["distillation"] = {
            "policy": (
                f"repo2run-{OPEN_PROGRAM_POLICY}"
                if self.candidate_interface == "open-program"
                else f"repo2run-{REPLAY_IR_POLICY}"
            ),
            "kept_count": len(distilled.kept_commands),
            "dropped_count": len(distilled.dropped_commands),
            "action_count": len(distilled.actions),
            "actions": [action.to_dict() for action in distilled.actions],
            "unsupported_commands": list(distilled.unsupported_commands),
        }
        if distilled.unsupported_commands:
            error = f"Repo2Run trajectory is not replayable: {list(distilled.unsupported_commands)}"
            return self._finish(
                artifacts, SolverResult(False, run_spec.method, error=error, metadata=metadata), log
            )

        write_text_atomic(artifacts.generated_script, distilled.script)
        trajectory_source = output_root / "track.json"
        trajectory_path = None
        if trajectory_source.is_file():
            write_text_atomic(artifacts.trajectory, trajectory_source.read_text(encoding="utf-8"))
            trajectory_path = str(artifacts.trajectory.relative_to(artifacts.root))
        result = SolverResult(
            True,
            run_spec.method,
            script_path=str(artifacts.generated_script.relative_to(artifacts.root)),
            trajectory_path=trajectory_path,
            metadata=metadata,
        )
        return self._finish(artifacts, result, log)
