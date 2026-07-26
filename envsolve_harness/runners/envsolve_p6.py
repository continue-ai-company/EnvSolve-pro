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
from envsolve.runtime.workspace import WorkspacePrecondition
from envsolve.runtime.goal import ExecutableGoalContract


METHOD_PROFILES = {
    "envsolve-pro": ("two-layer", "free-form"),
    "envsolve-pro-causal": ("two-layer", "free-form"),
    "envsolve-pro-no-retention": ("two-layer", "free-form"),
    "envsolve-pro-goal-aware-raw": ("goal-contract", "free-form"),
    "envsolve-pro-goal-contract": ("goal-contract", "free-form"),
    "envsolve-pro-goal-aware-raw-evidence": ("goal-contract", "free-form"),
    "envsolve-pro-goal-contract-evidence": ("goal-contract", "free-form"),
    "envsolve-pro-goal-aware-raw-evidence-anchor": (
        "goal-contract",
        "free-form",
    ),
    "envsolve-pro-goal-contract-evidence-anchor": (
        "goal-contract",
        "free-form",
    ),
    "envsolve-pro-goal-aware-raw-evidence-anchor-persistent": (
        "goal-contract",
        "free-form",
    ),
    "envsolve-pro-goal-contract-evidence-anchor-persistent": (
        "goal-contract",
        "free-form",
    ),
    "envsolve-full": ("two-layer", "constraint-driven"),
    "envsolve-runtime-only": ("runtime-only", "constraint-driven"),
    "envsolve-operation": ("two-layer", "constraint-driven"),
    "envsolve-operation-ablation": ("two-layer", "free-form"),
}
METHOD_CONSTRAINT_PROFILES = {method: "flat" for method in METHOD_PROFILES}
METHOD_CONSTRAINT_PROFILES["envsolve-pro-causal"] = "causal-frontier"
METHOD_CONSTRAINT_PROFILES["envsolve-pro-goal-aware-raw"] = "raw-history"
METHOD_CONSTRAINT_PROFILES[
    "envsolve-pro-goal-aware-raw-evidence"
] = "raw-history"
METHOD_CONSTRAINT_PROFILES[
    "envsolve-pro-goal-aware-raw-evidence-anchor"
] = (
    "raw-history"
)
METHOD_CONSTRAINT_PROFILES["envsolve-pro-goal-aware-raw-evidence-anchor-persistent"] = (
    "raw-history"
)
METHOD_REPOSITORY_EVIDENCE_PROFILES = {
    method: (
        "constraint-routed"
        if method in {
            "envsolve-pro-goal-aware-raw-evidence",
            "envsolve-pro-goal-contract-evidence",
            "envsolve-pro-goal-aware-raw-evidence-anchor",
            "envsolve-pro-goal-contract-evidence-anchor",
            "envsolve-pro-goal-aware-raw-evidence-anchor-persistent",
            "envsolve-pro-goal-contract-evidence-anchor-persistent",
        }
        else "disabled"
    )
    for method in METHOD_PROFILES
}
METHOD_CANDIDATE_ANCHOR_PROFILES = {
    method: (
        "retained-admissible"
        if method in {
            "envsolve-pro-goal-aware-raw-evidence-anchor",
            "envsolve-pro-goal-contract-evidence-anchor",
            "envsolve-pro-goal-aware-raw-evidence-anchor-persistent",
            "envsolve-pro-goal-contract-evidence-anchor-persistent",
        }
        else "disabled"
    )
    for method in METHOD_PROFILES
}
METHOD_CANDIDATE_INTERFACES = {
    method: "open-program" if method.startswith("envsolve-pro") else "typed-replay"
    for method in METHOD_PROFILES
}
METHOD_CANDIDATE_RETENTION = {
    method: (
        "disabled" if method == "envsolve-pro-no-retention" else "best-admissible")
    for method in METHOD_PROFILES
}
METHOD_ENVIRONMENT_STRATEGIES = {
    method: (
        "postcondition-persistent"
        if method.endswith("-persistent")
        else "fresh-candidate"
    )
    for method in METHOD_PROFILES
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
        max_environments: int,
        max_commands: int,
        command_timeout: int,
        container_create_timeout: int,
        model_request_timeout: int,
        model_max_retries: int,
        model_max_output_tokens: int,
        model_reasoning_effort: str | None,
        model_response_format: str,
        max_model_requests: int,
        max_total_tokens: int,
        max_estimated_cost_usd: float,
        workspace_preconditions: tuple[WorkspacePrecondition, ...] = (),
        goal_contract: ExecutableGoalContract | None = None,
    ) -> None:
        self.envbench_root = envbench_root
        self.harness_root = harness_root
        self.source_cache_root = source_cache_root
        self.image = image
        self.pricing = pricing
        self.timeout = timeout
        self.max_candidates = max_candidates
        self.max_environments = max_environments
        self.max_commands = max_commands
        self.command_timeout = command_timeout
        self.container_create_timeout = container_create_timeout
        self.model_request_timeout = model_request_timeout
        self.model_max_retries = model_max_retries
        self.model_max_output_tokens = model_max_output_tokens
        self.model_reasoning_effort = model_reasoning_effort
        self.model_response_format = model_response_format
        self.max_model_requests = max_model_requests
        self.max_total_tokens = max_total_tokens
        self.max_estimated_cost_usd = max_estimated_cost_usd
        self.workspace_preconditions = workspace_preconditions
        self.goal_contract = goal_contract

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
        constraint_profile = METHOD_CONSTRAINT_PROFILES.get(run_spec.method)
        repository_evidence_profile = METHOD_REPOSITORY_EVIDENCE_PROFILES.get(run_spec.method
        )
        candidate_anchor_profile = METHOD_CANDIDATE_ANCHOR_PROFILES.get(
            run_spec.method
        )
        candidate_interface = METHOD_CANDIDATE_INTERFACES.get(run_spec.method)
        candidate_retention = METHOD_CANDIDATE_RETENTION.get(run_spec.method)
        environment_strategy = METHOD_ENVIRONMENT_STRATEGIES.get(run_spec.method)
        metadata = {
            "runner": "envsolve-p6",
            "runner_version": "0.2.0",
            "audit_requirements": {"online_budget": True},
            "official_evaluator_access": "post-episode-only",
            "max_candidates": self.max_candidates,
            "max_environments": self.max_environments,
            "max_commands": self.max_commands,
            "started_at": self._now(),
            "obligation_profile": obligation_profile,
            "operation_profile": operation_profile,
            "constraint_profile": constraint_profile,
            "repository_evidence_profile": repository_evidence_profile,
            "candidate_anchor_profile": candidate_anchor_profile,
            "candidate_interface": candidate_interface,
            "candidate_retention": candidate_retention,
            "workspace_preconditions": [
                item.to_dict() for item in self.workspace_preconditions
            ],
            "model_reasoning_effort": self.model_reasoning_effort,
            "model_response_format": self.model_response_format,
        }
        if environment_strategy != "fresh-candidate":
            metadata["environment_strategy"] = environment_strategy
        if obligation_profile is None:
            return self._failure(
                artifacts,
                run_spec,
                f"Unsupported EnvSolve method {run_spec.method!r}",
                "unsupported EnvSolve method\n",
                metadata,
            )
        if obligation_profile == "goal-contract" and self.goal_contract is None:
            return self._failure(
                artifacts,
                run_spec,
                "Benchmark adapter does not declare an executable goal contract",
                "missing executable goal contract\n",
                metadata,
            )
        if not run_spec.model:
            return self._failure(
                artifacts, run_spec, "EnvSolve requires RunSpec.model", "missing model\n", metadata,
            )
        if not os.environ.get("OPENAI_API_KEY"):
            return self._failure(
                artifacts, run_spec, "OPENAI_API_KEY is not set", "missing API key\n", metadata,
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
            "--max-environments", str(self.max_environments),
            "--max-commands", str(self.max_commands),
            "--wall-clock-timeout", str(self.timeout),
            "--container-create-timeout", str(self.container_create_timeout),
            "--command-timeout", str(self.command_timeout),
            "--obligation-profile", obligation_profile,
            "--operation-profile", operation_profile,
            "--constraint-profile", constraint_profile,
            "--repository-evidence-profile", repository_evidence_profile,
            "--candidate-anchor-profile", candidate_anchor_profile,
            "--candidate-interface", candidate_interface,
            "--candidate-retention", candidate_retention,
            "--environment-strategy",
            environment_strategy,
            "--request-timeout", str(self.model_request_timeout),
            "--max-retries", str(self.model_max_retries),
            "--max-output-tokens", str(self.model_max_output_tokens),
            "--response-format", self.model_response_format,
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
        if obligation_profile == "goal-contract":
            goal_contract_path = artifacts.generation_dir / "goal_contract.json"
            write_json(goal_contract_path, self.goal_contract.to_dict())
            command.extend(["--goal-contract", str(goal_contract_path)])
            metadata["goal_contract"] = {
                "contract_id": self.goal_contract.contract_id,
                "report_schema": self.goal_contract.report_schema,
                "sha256": self.goal_contract.sha256,
            }
        for precondition in self.workspace_preconditions:
            if precondition.kind == "directory":
                command.extend(["--pre-bootstrap-directory", precondition.path])
        if self.model_reasoning_effort is not None:
            command.extend(["--reasoning-effort", self.model_reasoning_effort])
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
