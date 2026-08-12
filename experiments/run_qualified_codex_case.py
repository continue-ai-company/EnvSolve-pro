#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

# ruff: noqa: E402 - register experimental runners before CLI parsing.

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
from envsolve_harness.runners.codex_cli_qualified import (
    QualifiedCodexCliRunner,
    QualifiedEnvSolveProMinimalBRunner,
)
from envsolve_harness.runners.envsolve_pro_minimal_b import METHOD as MINIMAL_B_METHOD
from envsolve_harness.runners.registry import (
    RunnerOptions,
    register_solver_runner,
    registered_solver_runners,
)

CONTROL_RUNNER = "codex-cli-qualified"
TREATMENT_RUNNER = "envsolve-pro-minimal-b-qualified"
CONTROL_METHOD = "codex-cli-goal-aware"


def _common(config: HarnessConfig, protocol: ExperimentProtocol) -> dict[str, object]:
    benchmark = config.benchmark(protocol.benchmark)
    image = benchmark.settings.get("image")
    if not isinstance(image, str) or not image:
        raise ValueError("Qualified Codex requires a benchmark image")
    contract = goal_contract_for(config, protocol)
    if contract is None:
        raise ValueError("Qualified Codex requires a public goal contract")
    configured = config.solver_roots.get("codex-cli")
    executable = configured or Path(
        "/Applications/ChatGPT.app/Contents/Resources/codex"
    )
    if executable.is_dir():
        executable = executable / "codex"
    return {
        "codex_executable": executable,
        "harness_root": config.workspace_root,
        "source_cache_root": config.runs_root / "_source_cache/repositories",
        "image": image,
        "timeout": config.generation_timeout,
        "command_timeout": config.bash_timeout,
        "container_create_timeout": config.create_container_timeout,
        "git_fetch_timeout": config.git_fetch_timeout,
        "reasoning_effort": config.model_reasoning_effort,
        "workspace_preconditions": workspace_preconditions_for(config, protocol),
        "goal_contract": contract,
    }


def _control_factory(
    config: HarnessConfig,
    protocol: ExperimentProtocol,
    run_spec: RunSpec,
    options: RunnerOptions,
) -> SolverRunner:
    if run_spec.method != CONTROL_METHOD:
        raise ValueError(f"Unsupported qualified control method {run_spec.method!r}")
    return QualifiedCodexCliRunner(**_common(config, protocol))


def _treatment_factory(
    config: HarnessConfig,
    protocol: ExperimentProtocol,
    run_spec: RunSpec,
    options: RunnerOptions,
) -> SolverRunner:
    if run_spec.method != MINIMAL_B_METHOD:
        raise ValueError(f"Unsupported qualified treatment method {run_spec.method!r}")
    return QualifiedEnvSolveProMinimalBRunner(**_common(config, protocol))


def main() -> int:
    registered_solver_runners()
    register_solver_runner(CONTROL_RUNNER, CONTROL_METHOD, _control_factory)
    register_solver_runner(TREATMENT_RUNNER, MINIMAL_B_METHOD, _treatment_factory)
    from experiments import run_case

    return run_case.main()


if __name__ == "__main__":
    raise SystemExit(main())
