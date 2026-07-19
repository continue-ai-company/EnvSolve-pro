from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess

from envsolve_harness.core.io import read_json, write_json, write_text_atomic
from envsolve_harness.core.models import Case, ModelPricing, RunSpec, SolverResult
from envsolve_harness.execution.batch import cleanup_case_containers
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import update_manifest


METHOD_PROFILES = {
    "envsolve-full": ("two-layer", "constraint-driven"),
    "envsolve-runtime-only": ("runtime-only", "constraint-driven"),
    "envsolve-operation": ("two-layer", "constraint-driven"),
    "envsolve-operation-ablation": ("two-layer", "free-form"),
}


class EnvSolveP6Runner:
    def __init__(
        self,
        *,
        envbench_root: Path,
        harness_root: Path,
        source_cache_root: Path,
        image: str,
        pricing: ModelPricing | None,
        timeout: int,
        max_candidates: int,
        command_timeout: int,
        container_create_timeout: int,
        model_request_timeout: int,
        model_max_retries: int,
        model_max_output_tokens: int,
        max_model_requests: int,
        max_total_tokens: int,
        max_estimated_cost_usd: float,
    ) -> None:
        self.envbench_root = envbench_root
        self.harness_root = harness_root
        self.source_cache_root = source_cache_root
        self.image = image
        self.pricing = pricing
        self.timeout = timeout
        self.max_candidates = max_candidates
        self.command_timeout = command_timeout
        self.container_create_timeout = container_create_timeout
        self.model_request_timeout = model_request_timeout
        self.model_max_retries = model_max_retries
        self.model_max_output_tokens = model_max_output_tokens
        self.max_model_requests = max_model_requests
        self.max_total_tokens = max_total_tokens
        self.max_estimated_cost_usd = max_estimated_cost_usd

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _redact(value: str) -> str:
        return re.sub(
            r"(?<![A-Za-z0-9])sk-(?:proj-|or-v1-)?[A-Za-z0-9_-]{16,}",
            "[REDACTED]",
            value,
        )

    @staticmethod
    def _acquisition_infrastructure_failure(log: str) -> str | None:
        if "Unable to acquire the requested repository revision" not in log:
            return None
        if any(
            marker in log
            for marker in (
                "ReadTimeout",
                "ConnectionError",
                "Could not resolve host",
                "Temporary failure in name resolution",
            )
        ):
            return "repository-acquisition-network"
        return None

    def _failure(
        self,
        artifacts: RunArtifacts,
        run_spec: RunSpec,
        error: str,
        log: str,
        metadata: dict,
    ) -> SolverResult:
        result = SolverResult(
            False,
            run_spec.method,
            error=error,
            metadata={**metadata, "finished_at": self._now()},
        )
        if artifacts.budget_ledger.is_file():
            result.metadata["online_budget"] = read_json(artifacts.budget_ledger)
        write_json(artifacts.solver_result, result.to_dict())
        write_text_atomic(artifacts.solver_log, self._redact(log))
        update_manifest(artifacts, solver=result.to_dict())
        write_json(artifacts.status, {"state": "failed", "updated_at": self._now()})
        return result

    def run(self, case: Case, artifacts: RunArtifacts, run_spec: RunSpec) -> SolverResult:
        profiles = METHOD_PROFILES.get(run_spec.method)
        obligation_profile = profiles[0] if profiles else None
        operation_profile = profiles[1] if profiles else None
        metadata = {
            "runner": "envsolve-p6",
            "runner_version": "0.1.0",
            "audit_requirements": {"online_budget": True},
            "official_evaluator_access": "post-episode-only",
            "max_candidates": self.max_candidates,
            "started_at": self._now(),
            "obligation_profile": obligation_profile,
            "operation_profile": operation_profile,
        }
        if obligation_profile is None:
            return self._failure(
                artifacts,
                run_spec,
                f"Unsupported EnvSolve method {run_spec.method!r}",
                "unsupported EnvSolve method\n",
                metadata,
            )
        if not run_spec.model:
            return self._failure(
                artifacts, run_spec, "EnvSolve requires RunSpec.model", "missing model\n", metadata
            )
        if not os.environ.get("OPENAI_API_KEY"):
            return self._failure(
                artifacts, run_spec, "OPENAI_API_KEY is not set", "missing API key\n", metadata
            )
        if self.pricing is None or self.pricing.model != run_spec.model:
            return self._failure(
                artifacts,
                run_spec,
                f"Frozen model pricing is not configured for {run_spec.model!r}",
                "missing frozen model pricing\n",
                metadata,
            )
        python = self.envbench_root / ".venv/bin/python"
        command = [
            str(python),
            str(self.harness_root / "envsolve/tools/run_envsolve_episode.py"),
            "--repository", case.repository,
            "--revision", case.revision,
            "--case-id", case.case_id,
            "--run-id", run_spec.run_id,
            "--method", run_spec.method,
            "--model", run_spec.model,
            "--image", self.image,
            "--artifacts-root", str(artifacts.root),
            "--source-cache", str(self.source_cache_root),
            "--worktrees", str(artifacts.generation_dir / "worktrees"),
            "--ledger", str(artifacts.budget_ledger),
            "--max-candidates", str(self.max_candidates),
            "--wall-clock-timeout", str(self.timeout),
            "--container-create-timeout", str(self.container_create_timeout),
            "--command-timeout", str(self.command_timeout),
            "--obligation-profile", obligation_profile,
            "--operation-profile", operation_profile,
            "--request-timeout", str(self.model_request_timeout),
            "--max-retries", str(self.model_max_retries),
            "--max-output-tokens", str(self.model_max_output_tokens),
            "--max-model-requests", str(self.max_model_requests),
            "--max-total-tokens", str(self.max_total_tokens),
            "--max-cost-usd", str(self.max_estimated_cost_usd),
            "--input-cost", str(self.pricing.input_cost_per_million),
            "--output-cost", str(self.pricing.output_cost_per_million),
            "--cache-read-cost", str(
                self.pricing.cache_read_cost_per_million
                if self.pricing.cache_read_cost_per_million is not None
                else self.pricing.input_cost_per_million
            ),
        ]
        if self.pricing.source_url:
            command.extend(["--pricing-source-url", self.pricing.source_url])
        if self.pricing.snapshot_date:
            command.extend(["--pricing-snapshot-date", self.pricing.snapshot_date])
        if run_spec.seed is not None:
            command.extend(["--seed", str(run_spec.seed)])
        process_env = os.environ.copy()
        existing = process_env.get("PYTHONPATH")
        process_env["PYTHONPATH"] = (
            f"{self.harness_root}{os.pathsep}{existing}"
            if existing
            else str(self.harness_root)
        )
        try:
            process = subprocess.run(
                command,
                cwd=self.harness_root,
                env=process_env,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout + 300,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            cleaned = cleanup_case_containers(artifacts.root)
            metadata["cleaned_container_ids"] = list(cleaned)
            return self._failure(
                artifacts,
                run_spec,
                f"{type(exc).__name__}: {exc}",
                f"{type(exc).__name__}: {exc}\n",
                metadata,
            )
        log = f"$ {' '.join(command)}\n\n[stdout]\n{process.stdout}\n[stderr]\n{process.stderr}"
        if not artifacts.solver_result.is_file():
            acquisition_failure = self._acquisition_infrastructure_failure(log)
            if acquisition_failure is not None:
                metadata["infrastructure_stage"] = "repository_acquisition"
                metadata["infrastructure_signature"] = acquisition_failure
            return self._failure(
                artifacts,
                run_spec,
                (
                    "Repository acquisition was blocked by infrastructure failure"
                    if acquisition_failure is not None
                    else f"EnvSolve episode exited with {process.returncode} without a result"
                ),
                log,
                metadata,
            )
        value = read_json(artifacts.solver_result)
        result = SolverResult(**value)
        result.metadata.update(
            {
                "launcher": metadata,
                "process_exit_code": process.returncode,
            }
        )
        write_json(artifacts.solver_result, result.to_dict())
        write_text_atomic(artifacts.solver_log, self._redact(log))
        update_manifest(artifacts, solver=result.to_dict())
        return result
