from __future__ import annotations

import os
import subprocess

from envsolve_harness.core.io import (
    read_json,
    write_json,
    write_text_atomic,
)
from envsolve_harness.core.models import Case, RunSpec, SolverResult
from envsolve_harness.execution.batch import cleanup_case_containers
from envsolve_harness.runners.envsolve_pro import EnvSolveProRunner
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import update_manifest


METHOD = "envsolve-pro-goal-frontier"
METHOD_PROFILE = {
    "obligation_profile": "goal-contract",
    "operation_profile": "open-program",
    "constraint_profile": "goal-obligation-frontier-v1",
    "base_constraint_profile": "flat",
    "repository_evidence_profile": "constraint-routed",
    "candidate_anchor_profile": "retained-admissible",
    "candidate_interface": "open-program",
    "candidate_retention": "best-admissible",
    "environment_strategy": "fresh-candidate",
}


class EnvSolveProGoalFrontierRunner(EnvSolveProRunner):
    """Launcher isolated from the frozen operation-contract baseline."""

    episode_tool = "run_envsolve_goal_frontier_episode.py"

    def run(
        self,
        case: Case,
        artifacts: RunArtifacts,
        run_spec: RunSpec,
    ) -> SolverResult:
        metadata = {
            "runner": "envsolve-pro-goal-frontier",
            "runner_version": "0.1.0",
            "audit_requirements": {"online_budget": True},
            "official_evaluator_access": "post-episode-only",
            "max_candidates": self.max_candidates,
            "max_environments": self.max_environments,
            "max_commands": self.max_commands,
            "started_at": self._now(),
            **METHOD_PROFILE,
            "workspace_preconditions": [
                item.to_dict() for item in self.workspace_preconditions
            ],
            "model_reasoning_effort": self.model_reasoning_effort,
            "model_response_format": self.model_response_format,
        }
        if run_spec.method != METHOD:
            return self._failure(
                artifacts,
                run_spec,
                f"Unsupported EnvSolve-Pro method {run_spec.method!r}",
                "unsupported EnvSolve-Pro method\n",
                metadata,
            )
        if self.goal_contract is None:
            return self._failure(
                artifacts,
                run_spec,
                "Benchmark adapter does not declare an executable goal contract",
                "missing executable goal contract\n",
                metadata,
            )
        if not run_spec.model:
            return self._failure(
                artifacts,
                run_spec,
                "EnvSolve-Pro requires RunSpec.model",
                "missing model\n",
                metadata,
            )
        if not os.environ.get("OPENAI_API_KEY"):
            return self._failure(
                artifacts,
                run_spec,
                "OPENAI_API_KEY is not set",
                "missing API key\n",
                metadata,
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
            str(
                self.harness_root
                / f"envsolve/tools/{self.episode_tool}"
            ),
            "--repository",
            case.repository,
            "--revision",
            case.revision,
            "--case-id",
            case.case_id,
            "--run-id",
            run_spec.run_id,
            "--method",
            run_spec.method,
            "--model",
            run_spec.model,
            "--image",
            self.image,
            "--artifacts-root",
            str(artifacts.root),
            "--source-cache",
            str(self.source_cache_root),
            "--worktrees",
            str(artifacts.generation_dir / "worktrees"),
            "--ledger",
            str(artifacts.budget_ledger),
            "--max-candidates",
            str(self.max_candidates),
            "--max-environments",
            str(self.max_environments),
            "--max-commands",
            str(self.max_commands),
            "--wall-clock-timeout",
            str(self.timeout),
            "--container-create-timeout",
            str(self.container_create_timeout),
            "--command-timeout",
            str(self.command_timeout),
            "--obligation-profile",
            METHOD_PROFILE["obligation_profile"],
            "--operation-profile",
            "free-form",
            "--constraint-profile",
            METHOD_PROFILE["base_constraint_profile"],
            "--repository-evidence-profile",
            METHOD_PROFILE["repository_evidence_profile"],
            "--candidate-anchor-profile",
            METHOD_PROFILE["candidate_anchor_profile"],
            "--candidate-interface",
            METHOD_PROFILE["candidate_interface"],
            "--candidate-retention",
            METHOD_PROFILE["candidate_retention"],
            "--environment-strategy",
            METHOD_PROFILE["environment_strategy"],
            "--request-timeout",
            str(self.model_request_timeout),
            "--max-retries",
            str(self.model_max_retries),
            "--max-output-tokens",
            str(self.model_max_output_tokens),
            "--response-format",
            self.model_response_format,
            "--max-model-requests",
            str(self.max_model_requests),
            "--max-total-tokens",
            str(self.max_total_tokens),
            "--max-cost-usd",
            str(self.max_estimated_cost_usd),
            "--input-cost",
            str(self.pricing.input_cost_per_million),
            "--output-cost",
            str(self.pricing.output_cost_per_million),
            "--cache-read-cost",
            str(
                self.pricing.cache_read_cost_per_million
                if self.pricing.cache_read_cost_per_million is not None
                else self.pricing.input_cost_per_million
            ),
        ]
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
                command.extend(
                    ["--pre-bootstrap-directory", precondition.path]
                )
        if self.model_reasoning_effort is not None:
            command.extend(
                ["--reasoning-effort", self.model_reasoning_effort]
            )
        if self.pricing.source_url:
            command.extend(
                ["--pricing-source-url", self.pricing.source_url]
            )
        if self.pricing.snapshot_date:
            command.extend(
                ["--pricing-snapshot-date", self.pricing.snapshot_date]
            )
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
        log = (
            f"$ {' '.join(command)}\n\n[stdout]\n{process.stdout}"
            f"\n[stderr]\n{process.stderr}"
        )
        if not artifacts.solver_result.is_file():
            acquisition_failure = self._acquisition_infrastructure_failure(log)
            if acquisition_failure is not None:
                metadata["infrastructure_stage"] = "repository_acquisition"
                metadata["infrastructure_signature"] = acquisition_failure
            error = (
                "Repository acquisition was blocked by infrastructure failure"
                if acquisition_failure is not None
                else (
                    "EnvSolve-Pro episode exited with "
                    f"{process.returncode} without a result"
                )
            )
            return self._failure(
                artifacts,
                run_spec,
                error,
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
