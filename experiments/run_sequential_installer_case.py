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
from envsolve_harness.runners.registry import (
    RunnerOptions,
    register_solver_runner,
    registered_solver_runners,
)
from envsolve_harness.runners.sequential_installer import (
    INSTALLER_METHODS,
    InstallerArm,
    SequentialInstallerRunner,
)
from experiments.run_project_progress_case import _path, _required
from experiments.run_qualified_codex_case import _common
from experiments.run_remote_boundary_v6_case import _enabled, _optional_port


def _arm() -> InstallerArm:
    value = _required("ENVSOLVE_INSTALLER_ARM")
    if value not in INSTALLER_METHODS:
        raise ValueError("ENVSOLVE_INSTALLER_ARM must be static or adaptive")
    return cast(InstallerArm, value)


def _factory(
    config: HarnessConfig,
    protocol: ExperimentProtocol,
    run_spec: RunSpec,
    options: RunnerOptions,
) -> SequentialInstallerRunner:
    del options
    arm = _arm()
    expected_method = INSTALLER_METHODS[arm]
    if run_spec.method != expected_method:
        raise ValueError(
            f"Unexpected method {run_spec.method!r}; expected {expected_method!r}"
        )
    common = _common(config, protocol)
    update_state = _enabled("ENVSOLVE_PROGRESS_UPDATE_STATE")
    state_output = (
        _path("ENVSOLVE_PROGRESS_STATE_OUTPUT_ROOT") if update_state else None
    )
    return SequentialInstallerRunner(
        **common,
        installer_arm=arm,
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
        update_state=update_state,
        state_output_root=state_output,
        ssh_target=_required("ENVSOLVE_REMOTE_DOCKER_TARGET"),
        remote_workspace_root=os.environ.get(
            "ENVSOLVE_REMOTE_WORKSPACE_ROOT",
            "/home/avdpro/work/envsolve-pro-sequential-installer",
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
        SequentialInstallerRunner.runner_name,
        INSTALLER_METHODS[arm],
        _factory,
    )
    from experiments import run_case

    return run_case.main()


if __name__ == "__main__":
    raise SystemExit(main())
