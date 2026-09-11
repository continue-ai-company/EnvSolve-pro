#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.models import HarnessConfig, RunSpec
from envsolve_harness.core.protocol import ExperimentProtocol
from envsolve_harness.runners.base import SolverRunner
from envsolve_harness.runners.certification_repair_boundary_v6 import (
    CONTROL_METHOD,
    MINIMAL_B_METHOD,
)
from envsolve_harness.runners.official_path_replay import (
    RemoteOfficialPathMinimalBRunner,
)
from envsolve_harness.runners.registry import (
    RunnerOptions,
    register_solver_runner,
    registered_solver_runners,
)
from envsolve_harness.runners.remote_boundary_v6 import (
    OfficialPrimaryRemoteBoundaryV6CodexCliRunner,
)
from experiments.run_qualified_codex_case import _common
from experiments.run_remote_boundary_v6_case import _enabled, _optional_port


def _remote_common(config: HarnessConfig) -> dict[str, object]:
    target = os.environ.get("ENVSOLVE_REMOTE_DOCKER_TARGET", "").strip()
    if not target:
        raise ValueError("ENVSOLVE_REMOTE_DOCKER_TARGET is required")
    return {
        "ssh_target": target,
        "remote_workspace_root": os.environ.get(
            "ENVSOLVE_REMOTE_WORKSPACE_ROOT",
            "/home/avdpro/work/envsolve-pro-remote",
        ).strip(),
        "expose_gpus": _enabled("ENVSOLVE_REMOTE_EXPOSE_GPUS"),
        "ssh_identity": (
            os.environ.get("ENVSOLVE_REMOTE_SSH_IDENTITY", "").strip() or None
        ),
        "ssh_port": _optional_port("ENVSOLVE_REMOTE_SSH_PORT"),
        "docker_executable": (
            os.environ.get("ENVSOLVE_REMOTE_DOCKER_EXECUTABLE", "").strip()
            or "docker"
        ),
    }


def _control_factory(
    config: HarnessConfig,
    protocol: ExperimentProtocol,
    run_spec: RunSpec,
    options: RunnerOptions,
) -> SolverRunner:
    del options
    if run_spec.method != CONTROL_METHOD:
        raise ValueError(f"Expected control method {CONTROL_METHOD!r}")
    return OfficialPrimaryRemoteBoundaryV6CodexCliRunner(
        **_common(config, protocol),
        **_remote_common(config),
    )


def _treatment_factory(
    config: HarnessConfig,
    protocol: ExperimentProtocol,
    run_spec: RunSpec,
    options: RunnerOptions,
) -> SolverRunner:
    del options
    if run_spec.method != MINIMAL_B_METHOD:
        raise ValueError(f"Expected treatment method {MINIMAL_B_METHOD!r}")
    benchmark = config.benchmark(protocol.benchmark)
    remote_envbench_root = benchmark.settings.get("remote_benchmark_root")
    remote_evaluation_root = benchmark.settings.get("remote_workspace_root")
    if not isinstance(remote_envbench_root, str) or not remote_envbench_root:
        raise ValueError("Treatment requires remote_benchmark_root")
    if not isinstance(remote_evaluation_root, str) or not remote_evaluation_root:
        raise ValueError("Treatment requires remote_workspace_root")
    if benchmark.settings.get("preseed_source_cache", False) is not False:
        raise ValueError("Official-path A/B currently requires unseeded source acquisition")
    return RemoteOfficialPathMinimalBRunner(
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
        OfficialPrimaryRemoteBoundaryV6CodexCliRunner.runner_name,
        CONTROL_METHOD,
        _control_factory,
    )
    register_solver_runner(
        RemoteOfficialPathMinimalBRunner.runner_name,
        MINIMAL_B_METHOD,
        _treatment_factory,
    )
    from experiments import run_case

    return run_case.main()


if __name__ == "__main__":
    raise SystemExit(main())
