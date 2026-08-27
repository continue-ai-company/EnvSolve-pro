from __future__ import annotations

from typing import Any

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.codex.container_mcp import ContainerMcpServer
from envsolve_harness.compatibility_ledger import CompatibilityLedgerService


CURRENT_GOAL_SCHEMA = "envsolve-current-goal-observation-v1"


def _current_goal_output(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    return {
        stream: (
            {key: item for key, item in details.items() if key != "sha256"}
            if isinstance(details, dict)
            else details
        )
        for stream, details in value.items()
    }


class CurrentGoalService:
    """Execute the trusted goal without retaining cross-call search state."""

    def __init__(
        self,
        contract: ExecutableGoalContract,
        terminal_server: ContainerMcpServer,
        project_root: str = "/data/project",
    ) -> None:
        self.contract = contract
        self.terminal_server = terminal_server
        self.project_root = project_root
        self.check_count = 0
        self.complete_check_count = 0
        self.pass_check_count = 0

    def check(self, call_id: str) -> dict[str, Any]:
        # A fresh transport service on every call prevents history from crossing checks.
        raw = CompatibilityLedgerService(
            self.contract,
            self.terminal_server,
            self.project_root,
        ).check(call_id)
        self.check_count += 1

        complete = raw.get("finding_set_complete") is True
        passed = raw.get("candidate_ready") is True
        if complete:
            self.complete_check_count += 1
        if passed:
            self.pass_check_count += 1

        current = raw.get("current")
        constraints = (
            current.get("obligations", []) if isinstance(current, dict) else []
        )
        if not isinstance(constraints, list):
            constraints = []

        result: dict[str, Any] = {
            "schema": CURRENT_GOAL_SCHEMA,
            "ok": raw.get("ok") is True,
            "advisory_only": True,
            "operation_constraints_added": False,
            "history_used": False,
            "stores_container_checkpoint": False,
            "goal_status": raw.get("goal_status", "unknown"),
            "finding_set_complete": complete,
            "candidate_ready": passed,
            "active_constraint_count": len(constraints),
            "active_constraints": constraints,
        }
        if "goal_output" in raw:
            result["goal_output"] = _current_goal_output(raw["goal_output"])
        for name in ("reason", "execution"):
            if name in raw:
                result[name] = raw[name]
        return result

    def metadata(self) -> dict[str, Any]:
        return {
            "schema": CURRENT_GOAL_SCHEMA,
            "check_count": self.check_count,
            "complete_check_count": self.complete_check_count,
            "pass_check_count": self.pass_check_count,
            "agent_invoked_only": True,
            "automatic_check_count": 0,
            "history_used": False,
            "cross_call_state_retained": False,
            "stores_container_checkpoint": False,
            "operation_constraints_added": False,
        }
