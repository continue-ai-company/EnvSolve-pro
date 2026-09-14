#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.models import HarnessConfig, RunSpec
from envsolve_harness.core.protocol import ExperimentProtocol
from envsolve_harness.runners.base import SolverRunner
from envsolve_harness.runners.matched_official_replay import (
    REAL_METHOD,
    WITHHELD_METHOD,
    RemoteOfficialPathMatchedReplayRealRunner,
    RemoteOfficialPathMatchedReplayWithheldRunner,
)
from envsolve_harness.runners.registry import (
    RunnerOptions,
    register_solver_runner,
    registered_solver_runners,
)
from experiments.run_qualified_codex_case import _common
from experiments.run_remote_official_path_ab_case import _remote_common


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
            f"Unsupported matched official-path method {run_spec.method!r}; "
            f"expected {expected_method!r}"
        )
    benchmark = config.benchmark(protocol.benchmark)
    remote_envbench_root = benchmark.settings.get("remote_benchmark_root")
    remote_evaluation_root = benchmark.settings.get("remote_workspace_root")
    if not isinstance(remote_envbench_root, str) or not remote_envbench_root:
        raise ValueError("Matched replay requires remote_benchmark_root")
    if not isinstance(remote_evaluation_root, str) or not remote_evaluation_root:
        raise ValueError("Matched replay requires remote_workspace_root")
    return runner_type(
        **_common(config, protocol),
        **_remote_common(config),
        local_envbench_root=benchmark.root,
        remote_envbench_root=remote_envbench_root,
        remote_evaluation_root=remote_evaluation_root,
        evaluation_process_timeout=config.evaluation_process_timeout,
        evaluation_container_timeout=config.container_timeout,
        evaluation_max_workers=config.max_workers,
    )


def main() -> int:
    registered_solver_runners()
    register_solver_runner(
        RemoteOfficialPathMatchedReplayRealRunner.runner_name,
        REAL_METHOD,
        lambda config, protocol, run_spec, options: _factory(
            RemoteOfficialPathMatchedReplayRealRunner,
            REAL_METHOD,
            config,
            protocol,
            run_spec,
            options,
        ),
    )
    register_solver_runner(
        RemoteOfficialPathMatchedReplayWithheldRunner.runner_name,
        WITHHELD_METHOD,
        lambda config, protocol, run_spec, options: _factory(
            RemoteOfficialPathMatchedReplayWithheldRunner,
            WITHHELD_METHOD,
            config,
            protocol,
            run_spec,
            options,
        ),
    )
    from experiments import run_case

    return run_case.main()


if __name__ == "__main__":
    raise SystemExit(main())
