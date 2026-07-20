from __future__ import annotations

import json
from pathlib import Path

from envsolve_harness.core.models import BenchmarkConfig, HarnessConfig, ModelPricing


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_harness_config(path: Path, workspace_root: Path) -> HarnessConfig:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    benchmarks: dict[str, BenchmarkConfig] = {}
    for benchmark_id, raw in value.get("benchmarks", {}).items():
        benchmarks[benchmark_id] = BenchmarkConfig(
            benchmark_id=benchmark_id,
            adapter=str(raw.get("adapter", benchmark_id)),
            root=_resolve(workspace_root, str(raw["root"])).resolve(),
            settings=dict(raw.get("settings", {})),
        )
    solver_roots = {
        solver_id: _resolve(workspace_root, str(raw["root"])).resolve()
        for solver_id, raw in value.get("solvers", {}).items()
    }
    model_pricing = {
        model: ModelPricing(model=model, **raw)
        for model, raw in value.get("model_pricing", {}).items()
    }
    generation = value.get("generation", {})
    evaluation = value["evaluation"]
    envsolve_max_candidates = int(generation.get("envsolve_max_candidates", 5))
    return HarnessConfig(
        workspace_root=workspace_root,
        runs_root=_resolve(workspace_root, value["paths"]["runs"]).resolve(),
        benchmarks=benchmarks,
        solver_roots=solver_roots,
        model_pricing=model_pricing,
        create_container_timeout=int(evaluation["create_container_timeout"]),
        container_timeout=int(evaluation["container_timeout"]),
        max_workers=int(evaluation["max_workers"]),
        generation_timeout=int(generation.get("timeout", 7200)),
        model_request_timeout=int(generation.get("model_request_timeout", 180)),
        model_max_retries=int(generation.get("model_max_retries", 2)),
        model_max_output_tokens=int(generation.get("model_max_output_tokens", 16384)),
        model_reasoning_effort=(
            str(generation["model_reasoning_effort"])
            if generation.get("model_reasoning_effort") is not None
            else None
        ),
        model_response_format=str(generation.get("model_response_format", "text")),
        model_max_requests=int(generation.get("model_max_requests", 30)),
        model_max_total_tokens=int(generation.get("model_max_total_tokens", 1_000_000)),
        model_max_estimated_cost_usd=float(
            generation.get("model_max_estimated_cost_usd", 5.0)
        ),
        agent_max_iterations=int(generation.get("max_iterations", 30)),
        envsolve_max_candidates=envsolve_max_candidates,
        envsolve_max_environments=int(
            generation.get("envsolve_max_environments", envsolve_max_candidates)
        ),
        envsolve_max_commands=int(
            generation.get("envsolve_max_commands", envsolve_max_candidates)
        ),
        bash_timeout=int(generation.get("bash_timeout", 900)),
        evaluation_process_timeout=int(evaluation.get("process_timeout", 1800)),
        git_fetch_timeout=int(evaluation.get("git_fetch_timeout", 300)),
    )
