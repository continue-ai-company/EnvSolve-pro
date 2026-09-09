#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import cast

# ruff: noqa: E402 - register the experimental runner before CLI parsing.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.models import HarnessConfig, RunSpec
from envsolve_harness.core.protocol import ExperimentProtocol
from envsolve_harness.progress_state import DeploymentCondition
from envsolve_harness.runners.progress_agent import (
    PROGRESS_METHODS,
    ProgressAgentRunner,
    ProgressArm,
)
from envsolve_harness.runners.registry import (
    RunnerOptions,
    register_solver_runner,
    registered_solver_runners,
)
from experiments.run_qualified_codex_case import _common
from experiments.run_remote_boundary_v6_case import _enabled, _optional_port


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _path(name: str) -> Path:
    value = Path(_required(name)).expanduser()
    return value if value.is_absolute() else ROOT / value


def _arm() -> ProgressArm:
    value = _required("ENVSOLVE_PROGRESS_ARM")
    if value not in PROGRESS_METHODS:
        raise ValueError("ENVSOLVE_PROGRESS_ARM must be R0, R1, or P")
    return cast(ProgressArm, value)


def _factory(
    config: HarnessConfig,
    protocol: ExperimentProtocol,
    run_spec: RunSpec,
    options: RunnerOptions,
) -> ProgressAgentRunner:
    del options
    arm = _arm()
    expected_method = PROGRESS_METHODS[arm]
    if run_spec.method != expected_method:
        raise ValueError(
            f"Unexpected method {run_spec.method!r}; expected {expected_method!r}"
        )
    target = _required("ENVSOLVE_REMOTE_DOCKER_TARGET")
    common = _common(config, protocol)
    update_state = _enabled("ENVSOLVE_PROGRESS_UPDATE_STATE")
    state_output = (
        _path("ENVSOLVE_PROGRESS_STATE_OUTPUT_ROOT") if update_state else None
    )
    return ProgressAgentRunner(
        **common,
        arm=arm,
        state_path=_path("ENVSOLVE_PROGRESS_STATE"),
        target_condition=DeploymentCondition(
            condition_id=_required("ENVSOLVE_PROGRESS_CONDITION_ID"),
            operating_system=os.environ.get(
                "ENVSOLVE_PROGRESS_OPERATING_SYSTEM", "linux"
            ),
            architecture=os.environ.get(
                "ENVSOLVE_PROGRESS_ARCHITECTURE", "arm64"
            ),
            python_version=_required("ENVSOLVE_PROGRESS_PYTHON"),
            image=str(common["image"]),
        ),
        source_session_id=(
            os.environ.get("ENVSOLVE_PROGRESS_SOURCE_SESSION_ID", "").strip()
            or None
        ),
        update_state=update_state,
        state_output_root=state_output,
        ssh_target=target,
        remote_workspace_root=os.environ.get(
            "ENVSOLVE_REMOTE_WORKSPACE_ROOT",
            "/home/avdpro/work/envsolve-pro-m1",
        ),
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
    arm = _arm()
    register_solver_runner(
        ProgressAgentRunner.runner_name,
        PROGRESS_METHODS[arm],
        _factory,
    )
    from experiments import run_case

    return run_case.main()


if __name__ == "__main__":
    raise SystemExit(main())
