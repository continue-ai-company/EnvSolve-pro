from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import subprocess

from envsolve_harness.core.io import read_json, read_jsonl, write_json, write_jsonl, write_text_atomic
from envsolve_harness.core.models import Case, ModelPricing, RunSpec, SolverResult
from envsolve_harness.execution.batch import cleanup_case_containers
from envsolve_harness.integrity.repository import inspect_repository
from envsolve_harness.scripts.envbench_trajectory import (
    TrajectoryDistillationResult,
    aggregate_token_usage,
    commands_from_trajectory,
    distill_envbench_commands,
)
from envsolve_harness.scripts.replay_actions import REPLAY_IR_POLICY
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import update_manifest
from envsolve_harness.utils.provenance import git_provenance, sha256_file


class EnvBenchAgentRunner:
    def __init__(
        self,
        envbench_root: Path,
        timeout: int = 7200,
        max_iterations: int = 30,
        bash_timeout: int = 900,
        model_request_timeout: int = 180,
        model_max_retries: int = 2,
        model_max_output_tokens: int = 16384,
        max_model_requests: int = 30,
        max_total_tokens: int = 1_000_000,
        max_estimated_cost_usd: float = 5.0,
        pricing: ModelPricing | None = None,
        harness_root: Path | None = None,
    ) -> None:
        self.envbench_root = envbench_root
        self.timeout = timeout
        self.max_iterations = max_iterations
        self.bash_timeout = bash_timeout
        self.model_request_timeout = model_request_timeout
        self.model_max_retries = model_max_retries
        self.model_max_output_tokens = model_max_output_tokens
        self.max_model_requests = max_model_requests
        self.max_total_tokens = max_total_tokens
        self.max_estimated_cost_usd = max_estimated_cost_usd
        self.pricing = pricing
        self.harness_root = harness_root or Path(__file__).resolve().parents[2]

    @property
    def runner_id(self) -> str:
        return "envbench-react-agent"

    @property
    def runner_version(self) -> str:
        return "0.3.0"

    @property
    def agent_label(self) -> str:
        return "EnvBench agent"

    @property
    def distillation_policy(self) -> str:
        return f"envbench-{REPLAY_IR_POLICY}"

    def _build_inference_command(
        self,
        python: Path,
        case: Case,
        run_spec: RunSpec,
        artifacts: RunArtifacts,
        trajectories_dir: Path,
        repos_dir: Path,
    ) -> list[str]:
        if self.pricing is None:
            raise ValueError("model pricing is required")
        command = [
            str(python),
            "inference/main.py",
            "data_source.type=local",
            f"data_source.local.path={artifacts.solver_input}",
            "hf.upload=false",
            f"logging_dir={trajectories_dir}",
            "max_concurrent=1",
            "rewrite_trajectories=true",
            f"+global_timeout={self.timeout}",
            f"agent.model.model={run_spec.model}",
            "agent.model._target_=envsolve_harness.budget.langchain.create_budgeted_chat_model",
            f"+agent.model.request_timeout={self.model_request_timeout}",
            f"+agent.model.max_retries={self.model_max_retries}",
            f"+agent.model.max_tokens={self.model_max_output_tokens}",
            f"+agent.model.budget_ledger_path={artifacts.budget_ledger}",
            f"+agent.model.budget_max_model_requests={self.max_model_requests}",
            f"+agent.model.budget_max_total_tokens={self.max_total_tokens}",
            f"+agent.model.budget_max_estimated_cost_usd={self.max_estimated_cost_usd}",
            f"+agent.model.budget_input_cost_per_million={self.pricing.input_cost_per_million}",
            f"+agent.model.budget_output_cost_per_million={self.pricing.output_cost_per_million}",
            "+agent.model.budget_cache_read_cost_per_million="
            f"{self.pricing.cache_read_cost_per_million or self.pricing.input_cost_per_million}",
            f"agent.max_iterations={self.max_iterations}",
            f"docker.output_dir={repos_dir}",
            "docker.clear_repo=false",
            f"docker.bash_timeout={self.bash_timeout}",
            "docker.max_num_chars_bash_output=16000",
        ]
        if run_spec.seed is not None:
            command.append(f"+agent.model.seed={run_spec.seed}")
        if self.pricing.source_url:
            command.append(
                f"+agent.model.budget_pricing_source_url={self.pricing.source_url}"
            )
        if self.pricing.snapshot_date:
            command.append(
                f"+agent.model.budget_pricing_snapshot_date={self.pricing.snapshot_date}"
            )
        return command

    def _finalize_records(
        self,
        records: list[dict],
        project_directory: str,
    ) -> tuple[TrajectoryDistillationResult | None, str | None, dict]:
        commands = commands_from_trajectory(records)
        distilled = distill_envbench_commands(
            commands,
            project_directory=project_directory,
        )
        if distilled.unknown_commands:
            return (
                distilled,
                f"trajectory contains unsupported commands: {list(distilled.unknown_commands)}",
                {},
            )
        if not distilled.kept_commands:
            return distilled, "trajectory contains no replayable environment changes", {}
        return distilled, None, {}

    @staticmethod
    def _redact(value: str, secret: str | None) -> str:
        if secret:
            value = value.replace(secret, "[REDACTED]")
        return re.sub(
            r"(?<![A-Za-z0-9])sk-(?:proj-|or-v1-)?[A-Za-z0-9_-]{16,}",
            "[REDACTED]",
            value,
        )

    def _finish(self, artifacts: RunArtifacts, result: SolverResult, log: str) -> SolverResult:
        if artifacts.budget_ledger.is_file():
            ledger = read_json(artifacts.budget_ledger)
            result.metadata["online_budget"] = ledger
            if ledger.get("termination") and "termination" not in result.metadata:
                result.metadata["termination"] = ledger["termination"]
        write_json(artifacts.solver_result, result.to_dict())
        write_text_atomic(artifacts.solver_log, self._redact(log, os.environ.get("OPENAI_API_KEY")))
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
        base_metadata = {
            "runner": self.runner_id,
            "runner_version": self.runner_version,
            "audit_requirements": {
                "repository_integrity": True,
                "online_budget": True,
            },
            "envbench": git_provenance(self.envbench_root),
            "callback_bridge": {
                "path": "envsolve_harness/budget/langchain.py",
                "sha256": sha256_file(
                    self.harness_root / "envsolve_harness/budget/langchain.py"
                ),
            },
            "timeout": self.timeout,
            "max_iterations": self.max_iterations,
            "bash_timeout": self.bash_timeout,
            "resource_budget": {
                "generation_wall_clock_seconds": self.timeout,
                "generation_process_hard_deadline_seconds": self.timeout + 300,
                "model_request_timeout_seconds": self.model_request_timeout,
                "model_max_retries": self.model_max_retries,
                "model_max_output_tokens_per_request": self.model_max_output_tokens,
                "model_max_requests": self.max_model_requests,
                "model_max_total_tokens": self.max_total_tokens,
                "model_max_estimated_cost_usd": self.max_estimated_cost_usd,
                "agent_max_iterations": self.max_iterations,
                "bash_command_timeout_seconds": self.bash_timeout,
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
                SolverResult(
                    False,
                    run_spec.method,
                    error=f"{self.agent_label} requires RunSpec.model",
                    metadata=base_metadata,
                ),
                f"{self.agent_label} requires a model identifier.\n",
            )
        if not os.environ.get("OPENAI_API_KEY"):
            return self._finish(
                artifacts,
                SolverResult(False, run_spec.method, error="OPENAI_API_KEY is not set", metadata=base_metadata),
                "OPENAI_API_KEY is not set. The key value is never recorded.\n",
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

        write_jsonl(
            artifacts.solver_input,
            [{"repository": case.repository, "revision": case.revision}],
        )
        trajectories_dir = artifacts.generation_dir / "trajectories"
        repos_dir = artifacts.generation_dir / "repos"
        python = self.envbench_root / ".venv/bin/python"
        command = self._build_inference_command(
            python, case, run_spec, artifacts, trajectories_dir, repos_dir
        )
        process_env = os.environ.copy()
        python_path = process_env.get("PYTHONPATH")
        process_env["PYTHONPATH"] = (
            f"{self.harness_root}{os.pathsep}{python_path}" if python_path else str(self.harness_root)
        )
        try:
            process = subprocess.run(
                command,
                cwd=self.envbench_root,
                env=process_env,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout + 300,
            )
            log = f"$ {' '.join(command)}\n\n[stdout]\n{process.stdout}\n[stderr]\n{process.stderr}"
        except (OSError, subprocess.TimeoutExpired) as exc:
            metadata = {**base_metadata, "finished_at": datetime.now(timezone.utc).isoformat()}
            if isinstance(exc, subprocess.TimeoutExpired):
                cleaned_container_ids = cleanup_case_containers(artifacts.root)
                metadata["termination"] = {
                    "kind": "budget_exhausted",
                    "scope": "generation_process_hard_deadline",
                    "limit_seconds": self.timeout + 300,
                    "agent_limit_seconds": self.timeout,
                    "cleaned_container_ids": list(cleaned_container_ids),
                }
            return self._finish(
                artifacts,
                SolverResult(False, run_spec.method, error=f"{type(exc).__name__}: {exc}", metadata=metadata),
                f"{type(exc).__name__}: {exc}\n",
            )

        trajectory_source = trajectories_dir / f"{case.repository.replace('/', '__')}@{case.revision}.jsonl"
        repo_path = repos_dir / f"{case.repository.replace('/', '__')}@{case.revision}"
        metadata = {
            **base_metadata,
            "command": command,
            "process_exit_code": process.returncode,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        if process.returncode != 0 or not trajectory_source.is_file():
            error = (
                f"{self.agent_label} exited with {process.returncode}; "
                f"trajectory exists={trajectory_source.is_file()}"
            )
            return self._finish(
                artifacts, SolverResult(False, run_spec.method, error=error, metadata=metadata), log
            )

        if not repo_path.is_dir():
            error = f"{self.agent_label} repository is missing: {repo_path}"
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
            error = f"{self.agent_label} repository integrity failed: {integrity.to_dict()['violations']}"
            return self._finish(
                artifacts, SolverResult(False, run_spec.method, error=error, metadata=metadata), log
            )

        shutil.copyfile(trajectory_source, artifacts.trajectory_jsonl)
        try:
            records = read_jsonl(artifacts.trajectory_jsonl)
            distilled, finalization_error, finalization_metadata = self._finalize_records(
                records,
                f"{case.repository.replace('/', '__')}@{case.revision}",
            )
        except (OSError, ValueError, TypeError) as exc:
            error = f"Invalid EnvBench trajectory: {type(exc).__name__}: {exc}"
            return self._finish(
                artifacts, SolverResult(False, run_spec.method, error=error, metadata=metadata), log
            )

        metadata["token_usage"] = aggregate_token_usage(records)
        metadata.update(finalization_metadata)
        if distilled is None:
            error = finalization_error or "trajectory finalization produced no script"
            return self._finish(
                artifacts, SolverResult(False, run_spec.method, error=error, metadata=metadata), log
            )
        metadata["distillation"] = {
            "policy": self.distillation_policy,
            "kept_count": len(distilled.kept_commands),
            "dropped_count": len(distilled.dropped_commands),
            "action_count": len(distilled.actions),
            "actions": [action.to_dict() for action in distilled.actions],
            "unsupported_count": len(distilled.unknown_commands),
            "unsupported_commands": list(distilled.unknown_commands),
            "unknown_count": len(distilled.unknown_commands),
            "unknown_commands": list(distilled.unknown_commands),
        }
        if finalization_error:
            error = finalization_error
            return self._finish(
                artifacts, SolverResult(False, run_spec.method, error=error, metadata=metadata), log
            )

        write_text_atomic(artifacts.generated_script, distilled.script)
        result = SolverResult(
            True,
            run_spec.method,
            script_path=str(artifacts.generated_script.relative_to(artifacts.root)),
            trajectory_path=str(artifacts.trajectory_jsonl.relative_to(artifacts.root)),
            metadata=metadata,
        )
        return self._finish(artifacts, result, log)
