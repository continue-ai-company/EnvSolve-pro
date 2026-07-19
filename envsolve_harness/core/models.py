from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Case:
    case_id: str
    repository: str
    revision: str
    language: str = "python"
    split: str = "dev"
    tags: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Case":
        repository = str(value["repository"])
        revision = str(value["revision"])
        return cls(
            case_id=str(value.get("case_id") or f"{repository}@{revision}"),
            repository=repository,
            revision=revision,
            language=str(value.get("language", "python")),
            split=str(value.get("split", "dev")),
            tags=tuple(str(tag) for tag in value.get("tags", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["tags"] = list(self.tags)
        return value


@dataclass(frozen=True)
class BenchmarkConfig:
    benchmark_id: str
    adapter: str
    root: Path
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelPricing:
    model: str
    input_cost_per_million: float
    output_cost_per_million: float
    cache_read_cost_per_million: float | None = None
    source_url: str | None = None
    snapshot_date: str | None = None

    def __post_init__(self) -> None:
        if self.input_cost_per_million < 0 or self.output_cost_per_million < 0:
            raise ValueError("Input and output model prices must be non-negative")
        if self.cache_read_cost_per_million is not None and self.cache_read_cost_per_million < 0:
            raise ValueError("Cache-read model price must be non-negative")


@dataclass(frozen=True)
class HarnessConfig:
    workspace_root: Path
    runs_root: Path
    benchmarks: dict[str, BenchmarkConfig] = field(default_factory=dict)
    solver_roots: dict[str, Path] = field(default_factory=dict)
    model_pricing: dict[str, ModelPricing] = field(default_factory=dict)
    create_container_timeout: int = 180
    container_timeout: int = 900
    max_workers: int = 1
    generation_timeout: int = 7200
    model_request_timeout: int = 180
    model_max_retries: int = 2
    model_max_output_tokens: int = 16384
    model_max_requests: int = 30
    model_max_total_tokens: int = 1_000_000
    model_max_estimated_cost_usd: float = 5.0
    agent_max_iterations: int = 30
    envsolve_max_candidates: int = 5
    envsolve_max_environments: int = 5
    envsolve_max_commands: int = 5
    bash_timeout: int = 900
    evaluation_process_timeout: int = 1800
    git_fetch_timeout: int = 300

    def benchmark(self, benchmark_id: str) -> BenchmarkConfig:
        try:
            return self.benchmarks[benchmark_id]
        except KeyError as exc:
            raise ValueError(f"Benchmark {benchmark_id!r} is not configured") from exc

    def solver_root(self, solver_id: str) -> Path:
        try:
            return self.solver_roots[solver_id]
        except KeyError as exc:
            raise ValueError(f"Solver {solver_id!r} is not configured") from exc

    def pricing_for(self, model: str) -> ModelPricing:
        try:
            return self.model_pricing[model]
        except KeyError as exc:
            raise ValueError(f"Model pricing for {model!r} is not configured") from exc

    def __post_init__(self) -> None:
        positive_limits = {
            "create_container_timeout": self.create_container_timeout,
            "container_timeout": self.container_timeout,
            "max_workers": self.max_workers,
            "generation_timeout": self.generation_timeout,
            "model_request_timeout": self.model_request_timeout,
            "model_max_output_tokens": self.model_max_output_tokens,
            "model_max_requests": self.model_max_requests,
            "model_max_total_tokens": self.model_max_total_tokens,
            "agent_max_iterations": self.agent_max_iterations,
            "envsolve_max_candidates": self.envsolve_max_candidates,
            "envsolve_max_environments": self.envsolve_max_environments,
            "envsolve_max_commands": self.envsolve_max_commands,
            "bash_timeout": self.bash_timeout,
            "evaluation_process_timeout": self.evaluation_process_timeout,
            "git_fetch_timeout": self.git_fetch_timeout,
        }
        invalid = {name: value for name, value in positive_limits.items() if value <= 0}
        if invalid:
            raise ValueError(f"Harness limits must be positive: {invalid}")
        if self.model_max_retries < 0:
            raise ValueError("model_max_retries must be non-negative")
        if self.model_max_estimated_cost_usd <= 0:
            raise ValueError("model_max_estimated_cost_usd must be positive")

    def resource_budget(self) -> dict[str, Any]:
        return {
            "generation_wall_clock_seconds": self.generation_timeout,
            "model_request_timeout_seconds": self.model_request_timeout,
            "model_max_retries": self.model_max_retries,
            "model_max_output_tokens_per_request": self.model_max_output_tokens,
            "model_max_requests": self.model_max_requests,
            "model_max_total_tokens": self.model_max_total_tokens,
            "model_max_estimated_cost_usd": self.model_max_estimated_cost_usd,
            "agent_max_iterations": self.agent_max_iterations,
            "envsolve_max_candidates": self.envsolve_max_candidates,
            "envsolve_max_environments": self.envsolve_max_environments,
            "envsolve_max_commands": self.envsolve_max_commands,
            "bash_command_timeout_seconds": self.bash_timeout,
            "evaluation_process_timeout_seconds": self.evaluation_process_timeout,
            "container_create_timeout_seconds": self.create_container_timeout,
            "container_execution_timeout_seconds": self.container_timeout,
            "git_fetch_timeout_seconds": self.git_fetch_timeout,
        }


@dataclass(frozen=True)
class RunSpec:
    run_id: str
    method: str
    model: str | None = None
    seed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SolverResult:
    generation_completed: bool
    method: str
    script_path: str | None = None
    trajectory_path: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationResult:
    evaluation_completed: bool
    official_pass: bool
    benchmark: str
    case_id: str
    execution_time: float | None
    evidence: tuple["VerificationEvidence", ...] = ()
    raw_metrics: dict[str, Any] = field(default_factory=dict)
    raw_result_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerificationEvidence:
    verifier_id: str
    channel: str
    passed: bool | None
    summary: str
    metrics: dict[str, Any] = field(default_factory=dict)
    artifact_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
