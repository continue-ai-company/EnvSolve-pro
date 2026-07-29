#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


# ruff: noqa: E402 - register the experimental runner before CLI parsing.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.adapters.registry import (
    goal_contract_for,
    workspace_preconditions_for,
)
from envsolve_harness.core.models import HarnessConfig, RunSpec
from envsolve_harness.core.protocol import ExperimentProtocol
from envsolve_harness.runners.base import SolverRunner
from envsolve_harness.runners.envsolve_pro_bootstrap_frontier import (
    METHOD,
    EnvSolveProBootstrapFrontierRunner,
)
from envsolve_harness.runners.registry import (
    RunnerOptions,
    register_solver_runner,
    registered_solver_runners,
)


RUNNER_ID = "envsolve-pro-bootstrap-frontier"


def _factory(
    config: HarnessConfig,
    protocol: ExperimentProtocol,
    run_spec: RunSpec,
    options: RunnerOptions,
) -> SolverRunner:
    benchmark = config.benchmark(protocol.benchmark)
    image = benchmark.settings.get("image")
    if not isinstance(image, str) or not image:
        raise ValueError(
            "EnvSolve-Pro bootstrap-frontier requires a benchmark execution image"
        )
    pricing = (
        config.model_pricing.get(run_spec.model)
        if run_spec.model
        else None
    )
    return EnvSolveProBootstrapFrontierRunner(
        envbench_root=config.solver_root("envbench-agent"),
        harness_root=config.workspace_root,
        source_cache_root=(
            config.runs_root / "_source_cache/envbench-python"
        ),
        image=image,
        pricing=pricing,
        timeout=config.generation_timeout,
        max_candidates=config.envsolve_max_candidates,
        max_environments=config.envsolve_max_environments,
        max_commands=config.envsolve_max_commands,
        command_timeout=config.bash_timeout,
        container_create_timeout=config.create_container_timeout,
        model_request_timeout=config.model_request_timeout,
        model_max_retries=config.model_max_retries,
        model_max_output_tokens=config.model_max_output_tokens,
        model_reasoning_effort=config.model_reasoning_effort,
        model_response_format=config.model_response_format,
        max_model_requests=config.model_max_requests,
        max_total_tokens=config.model_max_total_tokens,
        max_estimated_cost_usd=config.model_max_estimated_cost_usd,
        workspace_preconditions=workspace_preconditions_for(config, protocol),
        goal_contract=goal_contract_for(config, protocol),
    )


def main() -> int:
    registered_solver_runners()
    register_solver_runner(RUNNER_ID, METHOD, _factory)
    from experiments import run_case

    return run_case.main()


if __name__ == "__main__":
    raise SystemExit(main())
