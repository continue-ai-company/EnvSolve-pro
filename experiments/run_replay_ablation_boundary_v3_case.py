#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

# ruff: noqa: E402 - register experimental runners before CLI parsing.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.models import HarnessConfig, RunSpec
from envsolve_harness.core.protocol import ExperimentProtocol
from envsolve_harness.runners.base import SolverRunner
from envsolve_harness.runners.certification_repair_boundary_v3 import (
    CONTROL_METHOD,
    MINIMAL_B_METHOD,
    ONE_SHOT_METHOD,
    BoundaryV3QualifiedCodexCliRunner,
    BoundaryV3QualifiedMinimalBRunner,
    BoundaryV3QualifiedOneShotRunner,
)
from envsolve_harness.runners.registry import (
    RunnerOptions,
    register_solver_runner,
    registered_solver_runners,
)
from experiments.run_qualified_codex_case import _common


def _factory(
    runner_type: type[SolverRunner],
    expected_method: str,
    config: HarnessConfig,
    protocol: ExperimentProtocol,
    run_spec: RunSpec,
    options: RunnerOptions,
) -> SolverRunner:
    del options
    if run_spec.method != expected_method:
        raise ValueError(
            f"Unsupported boundary-v3 method {run_spec.method!r}; "
            f"expected {expected_method!r}"
        )
    return runner_type(**_common(config, protocol))


def main() -> int:
    registered_solver_runners()
    registrations = (
        (BoundaryV3QualifiedCodexCliRunner, CONTROL_METHOD),
        (BoundaryV3QualifiedOneShotRunner, ONE_SHOT_METHOD),
        (BoundaryV3QualifiedMinimalBRunner, MINIMAL_B_METHOD),
    )
    for runner_type, method in registrations:
        register_solver_runner(
            runner_type.runner_name,
            method,
            lambda config, protocol, run_spec, options, rt=runner_type, m=method: (
                _factory(rt, m, config, protocol, run_spec, options)
            ),
        )
    from experiments import run_case

    return run_case.main()


if __name__ == "__main__":
    raise SystemExit(main())
