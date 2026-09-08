from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.run_qualified_codex_case import _common
from experiments.run_remote_boundary_v6_case import _enabled, _optional_port
from envsolve_harness.runners.certification_repair_boundary_v6 import CONTROL_METHOD
from envsolve_harness.runners.free_agent_census import FreeAgentCensusRunner
from envsolve_harness.runners.registry import register_solver_runner, registered_solver_runners


def _factory(config, protocol, run_spec, options):
    if run_spec.method != CONTROL_METHOD:
        raise ValueError(f"Unexpected method: {run_spec.method}")
    target = os.environ.get("ENVSOLVE_REMOTE_DOCKER_TARGET", "").strip()
    if not target:
        raise ValueError("ENVSOLVE_REMOTE_DOCKER_TARGET is required")
    return FreeAgentCensusRunner(
        **_common(config, protocol), ssh_target=target,
        remote_workspace_root=os.environ.get("ENVSOLVE_REMOTE_WORKSPACE_ROOT", "/Users/agenthub/EnvSolve-pro-v7-construction"),
        expose_gpus=_enabled("ENVSOLVE_REMOTE_EXPOSE_GPUS"),
        ssh_identity=os.environ.get("ENVSOLVE_REMOTE_SSH_IDENTITY") or None,
        ssh_port=_optional_port("ENVSOLVE_REMOTE_SSH_PORT"),
        docker_executable=os.environ.get("ENVSOLVE_REMOTE_DOCKER_EXECUTABLE", "docker"))


def main():
    registered_solver_runners()
    register_solver_runner(FreeAgentCensusRunner.runner_name, CONTROL_METHOD, _factory)
    from experiments import run_case
    return run_case.main()


if __name__ == "__main__":
    raise SystemExit(main())
