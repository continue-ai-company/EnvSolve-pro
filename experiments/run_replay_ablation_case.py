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
from envsolve_harness.runners.codex_cli_qualified import (
    QualifiedCodexCliRunner,
    QualifiedEnvSolveProMinimalBRunner,
)
from envsolve_harness.runners.envsolve_pro_minimal_b import METHOD as MINIMAL_B_METHOD
from envsolve_harness.runners.envsolve_pro_one_shot import (
    METHOD as ONE_SHOT_METHOD,
)
from envsolve_harness.runners.envsolve_pro_one_shot import (
    QualifiedEnvSolveProOneShotCertificationRunner,
)
from envsolve_harness.runners.registry import (
    RunnerOptions,
    register_solver_runner,
    registered_solver_runners,
)
from experiments.run_qualified_codex_case import (
    CONTROL_METHOD,
    CONTROL_RUNNER,
    TREATMENT_RUNNER,
    _common,
)

ONE_SHOT_RUNNER = "envsolve-pro-one-shot-certification-qualified"


def _control_factory(
    config: HarnessConfig,
    protocol: ExperimentProtocol,
    run_spec: RunSpec,
    options: RunnerOptions,
) -> SolverRunner:
    if run_spec.method != CONTROL_METHOD:
        raise ValueError(f"Unsupported qualified control method {run_spec.method!r}")
    return QualifiedCodexCliRunner(**_common(config, protocol))


def _one_shot_factory(
    config: HarnessConfig,
    protocol: ExperimentProtocol,
    run_spec: RunSpec,
    options: RunnerOptions,
) -> SolverRunner:
    if run_spec.method != ONE_SHOT_METHOD:
        raise ValueError(f"Unsupported one-shot method {run_spec.method!r}")
    return QualifiedEnvSolveProOneShotCertificationRunner(
        **_common(config, protocol)
    )


def _minimal_b_factory(
    config: HarnessConfig,
    protocol: ExperimentProtocol,
    run_spec: RunSpec,
    options: RunnerOptions,
) -> SolverRunner:
    if run_spec.method != MINIMAL_B_METHOD:
        raise ValueError(f"Unsupported Minimal B method {run_spec.method!r}")
    return QualifiedEnvSolveProMinimalBRunner(**_common(config, protocol))


def main() -> int:
    registered_solver_runners()
    register_solver_runner(CONTROL_RUNNER, CONTROL_METHOD, _control_factory)
    register_solver_runner(ONE_SHOT_RUNNER, ONE_SHOT_METHOD, _one_shot_factory)
    register_solver_runner(TREATMENT_RUNNER, MINIMAL_B_METHOD, _minimal_b_factory)
    from experiments import run_case

    return run_case.main()


if __name__ == "__main__":
    raise SystemExit(main())
