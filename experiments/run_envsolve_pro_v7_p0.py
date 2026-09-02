#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.models import HarnessConfig, RunSpec
from envsolve_harness.core.protocol import ExperimentProtocol
from envsolve_harness.runners.base import SolverRunner
from envsolve_harness.runners.certification_repair_boundary_v6 import CONTROL_METHOD
from envsolve_harness.runners.registry import (
    RunnerOptions,
    register_solver_runner,
    registered_solver_runners,
)
from envsolve_harness.runners.v7_persistent_codex import (
    V7PersistentP0RemoteCodexRunner,
)
from experiments.run_qualified_codex_case import _common
from experiments.run_remote_boundary_v6_case import _enabled, _optional_port


def _factory(
    config: HarnessConfig,
    protocol: ExperimentProtocol,
    run_spec: RunSpec,
    options: RunnerOptions,
) -> SolverRunner:
    del options
    if run_spec.method != CONTROL_METHOD:
        raise ValueError(
            f"Unsupported v7 P0 method {run_spec.method!r}; expected {CONTROL_METHOD!r}"
        )
    target = os.environ.get("ENVSOLVE_REMOTE_DOCKER_TARGET", "").strip()
    if not target:
        raise ValueError("ENVSOLVE_REMOTE_DOCKER_TARGET is required")
    remote_root = os.environ.get(
        "ENVSOLVE_REMOTE_WORKSPACE_ROOT",
        "/Users/agenthub/EnvSolve-pro-v7-construction",
    ).strip()
    return V7PersistentP0RemoteCodexRunner(
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
        V7PersistentP0RemoteCodexRunner.runner_name,
        CONTROL_METHOD,
        _factory,
    )
    from experiments import run_case

    return run_case.main()


if __name__ == "__main__":
    raise SystemExit(main())

