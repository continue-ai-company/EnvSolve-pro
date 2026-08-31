#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

# ruff: noqa: E402 - register the remote experimental runner before CLI parsing.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.models import HarnessConfig, RunSpec
from envsolve_harness.core.protocol import ExperimentProtocol
from envsolve_harness.runners.base import SolverRunner
from envsolve_harness.runners.certification_repair_boundary_v5 import (
    CONTROL_METHOD,
    MINIMAL_B_METHOD,
)
from envsolve_harness.runners.registry import (
    RunnerOptions,
    register_solver_runner,
    registered_solver_runners,
)
from envsolve_harness.runners.remote_boundary_v5 import (
    OfficialPrimaryRemoteBoundaryV5CodexCliRunner,
    RemoteBoundaryV5QualifiedCodexCliRunner,
    RemoteBoundaryV5QualifiedMinimalBRunner,
)
from experiments.run_qualified_codex_case import _common


def _enabled(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if value not in {"", "0", "1", "false", "true"}:
        raise ValueError(f"{name} must be true/false or 1/0")
    return value in {"1", "true"}


def _optional_port(name: str) -> int | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    port = int(value)
    if not 1 <= port <= 65535:
        raise ValueError(f"{name} must be between 1 and 65535")
    return port


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
            f"Unsupported remote boundary-v5 method {run_spec.method!r}; "
            f"expected {expected_method!r}"
        )
    target = os.environ.get("ENVSOLVE_REMOTE_DOCKER_TARGET", "").strip()
    if not target:
        raise ValueError("ENVSOLVE_REMOTE_DOCKER_TARGET is required")
    remote_root = os.environ.get(
        "ENVSOLVE_REMOTE_WORKSPACE_ROOT",
        "/home/avdpro/work/envsolve-pro-remote",
    ).strip()
    return runner_type(
        **_common(config, protocol),
        ssh_target=target,
        remote_workspace_root=remote_root,
        expose_gpus=_enabled("ENVSOLVE_REMOTE_EXPOSE_GPUS"),
        ssh_identity=(
            os.environ.get("ENVSOLVE_REMOTE_SSH_IDENTITY", "").strip() or None
        ),
        ssh_port=_optional_port("ENVSOLVE_REMOTE_SSH_PORT"),
        docker_executable=(
            os.environ.get("ENVSOLVE_REMOTE_DOCKER_EXECUTABLE", "").strip()
            or "docker"
        ),
    )


def main() -> int:
    registered_solver_runners()
    register_solver_runner(
        RemoteBoundaryV5QualifiedCodexCliRunner.runner_name,
        CONTROL_METHOD,
        lambda config, protocol, run_spec, options: _factory(
            RemoteBoundaryV5QualifiedCodexCliRunner,
            CONTROL_METHOD,
            config,
            protocol,
            run_spec,
            options,
        ),
    )
    register_solver_runner(
        OfficialPrimaryRemoteBoundaryV5CodexCliRunner.runner_name,
        CONTROL_METHOD,
        lambda config, protocol, run_spec, options: _factory(
            OfficialPrimaryRemoteBoundaryV5CodexCliRunner,
            CONTROL_METHOD,
            config,
            protocol,
            run_spec,
            options,
        ),
    )
    register_solver_runner(
        RemoteBoundaryV5QualifiedMinimalBRunner.runner_name,
        MINIMAL_B_METHOD,
        lambda config, protocol, run_spec, options: _factory(
            RemoteBoundaryV5QualifiedMinimalBRunner,
            MINIMAL_B_METHOD,
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
