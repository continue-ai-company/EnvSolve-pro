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
from envsolve_harness.runners.envsolve_pro_minimal_b import (
    METHOD,
    EnvSolveProMinimalBRunner,
)
from envsolve_harness.runners.registry import (
    RunnerOptions,
    register_solver_runner,
    registered_solver_runners,
)


RUNNER_ID = "envsolve-pro-minimal-b"


def _factory(
    config: HarnessConfig,
    protocol: ExperimentProtocol,
    run_spec: RunSpec,
    options: RunnerOptions,
) -> SolverRunner:
    if run_spec.method != METHOD:
        raise ValueError(f"Unsupported Minimal B method {run_spec.method!r}")
    benchmark = config.benchmark(protocol.benchmark)
    image = benchmark.settings.get("image")
    if not isinstance(image, str) or not image:
        raise ValueError("EnvSolve-Pro Minimal B requires a benchmark image")
    contract = goal_contract_for(config, protocol)
    if contract is None:
        raise ValueError("EnvSolve-Pro Minimal B requires a public goal contract")
    configured = config.solver_roots.get("codex-cli")
    executable = configured or Path(
        "/Applications/ChatGPT.app/Contents/Resources/codex"
    )
    if executable.is_dir():
        executable = executable / "codex"
    return EnvSolveProMinimalBRunner(
        codex_executable=executable,
        harness_root=config.workspace_root,
        image=image,
        timeout=config.generation_timeout,
        command_timeout=config.bash_timeout,
        container_create_timeout=config.create_container_timeout,
        git_fetch_timeout=config.git_fetch_timeout,
        reasoning_effort=config.model_reasoning_effort,
        workspace_preconditions=workspace_preconditions_for(config, protocol),
        goal_contract=contract,
    )


def main() -> int:
    registered_solver_runners()
    register_solver_runner(RUNNER_ID, METHOD, _factory)
    from experiments import run_case

    return run_case.main()


if __name__ == "__main__":
    raise SystemExit(main())
