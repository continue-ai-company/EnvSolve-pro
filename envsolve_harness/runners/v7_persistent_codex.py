from __future__ import annotations

from typing import Any

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.core.models import RunSpec
from envsolve_harness.runners.certification_repair_boundary_v6 import CONTROL_METHOD
from envsolve_harness.runners.remote_boundary_v6 import (
    OfficialPrimaryRemoteBoundaryV6CodexCliRunner,
)


class V7PersistentP0RemoteCodexRunner(
    OfficialPrimaryRemoteBoundaryV6CodexCliRunner
):
    """Run the shared strong-Agent control while retaining its Codex session."""

    runner_name = "envsolve-pro-v7-persistent-p0-remote-docker"
    runner_version = "7.0.0-pilot"

    def _goal_contract_for_run(
        self,
        run_spec: RunSpec,
    ) -> ExecutableGoalContract | None:
        return self.goal_contract if run_spec.method == CONTROL_METHOD else None

    def _codex_command(self, **kwargs: Any) -> list[str]:
        command = super()._codex_command(**kwargs)
        command.remove("--ephemeral")
        return command

