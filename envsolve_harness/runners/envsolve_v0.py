from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from envsolve.v0.finalization import finalize_v0_trajectory
from envsolve_harness.core.models import Case, RunSpec
from envsolve_harness.runners.envbench_agent import EnvBenchAgentRunner
from envsolve_harness.scripts.envbench_trajectory import TrajectoryDistillationResult
from envsolve_harness.scripts.replay_actions import REPLAY_IR_POLICY
from envsolve_harness.storage.artifacts import RunArtifacts


class EnvSolveV0Runner(EnvBenchAgentRunner):
    def __init__(self, envbench_root: Path, image: str, **kwargs) -> None:
        super().__init__(envbench_root, **kwargs)
        self.image = image

    @property
    def runner_id(self) -> str:
        return "envsolve-v0"

    @property
    def runner_version(self) -> str:
        return "0.1.0"

    @property
    def agent_label(self) -> str:
        return "EnvSolve v0"

    @property
    def distillation_policy(self) -> str:
        return f"envsolve-v0-{REPLAY_IR_POLICY}"

    def _build_inference_command(
        self,
        python: Path,
        case: Case,
        run_spec: RunSpec,
        artifacts: RunArtifacts,
        trajectories_dir: Path,
        repos_dir: Path,
    ) -> list[str]:
        if self.pricing is None or run_spec.model is None:
            raise ValueError("model and pricing are required")
        command = [
            str(python),
            str(self.harness_root / "envsolve/tools/run_v0_inference.py"),
            "--repository", case.repository,
            "--revision", case.revision,
            "--model", run_spec.model,
            "--image", self.image,
            "--trajectory-dir", str(trajectories_dir),
            "--repos-dir", str(repos_dir),
            "--ledger", str(artifacts.budget_ledger),
            "--max-iterations", str(self.max_iterations),
            "--bash-timeout", str(self.bash_timeout),
            "--request-timeout", str(self.model_request_timeout),
            "--max-retries", str(self.model_max_retries),
            "--max-output-tokens", str(self.model_max_output_tokens),
            "--max-model-requests", str(self.max_model_requests),
            "--max-total-tokens", str(self.max_total_tokens),
            "--max-cost-usd", str(self.max_estimated_cost_usd),
            "--input-cost", str(self.pricing.input_cost_per_million),
            "--output-cost", str(self.pricing.output_cost_per_million),
            "--cache-read-cost",
            str(self.pricing.cache_read_cost_per_million or self.pricing.input_cost_per_million),
        ]
        if self.pricing.source_url:
            command.extend(["--pricing-source-url", self.pricing.source_url])
        if self.pricing.snapshot_date:
            command.extend(["--pricing-snapshot-date", self.pricing.snapshot_date])
        if run_spec.seed is not None:
            command.extend(["--seed", str(run_spec.seed)])
        return command

    def _finalize_records(
        self,
        records: list[dict],
        project_directory: str,
    ) -> tuple[TrajectoryDistillationResult | None, str | None, dict]:
        finalized = finalize_v0_trajectory(records, project_directory)
        return (
            finalized.distillation,
            finalized.error,
            {"v0_completion": asdict(finalized.completion)},
        )
