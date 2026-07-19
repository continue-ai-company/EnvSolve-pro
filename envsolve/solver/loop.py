from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from envsolve.solver.session import (
    ActionExecutor,
    ActionSpec,
    SolverStateSession,
)
from envsolve.state import EnvironmentState


@dataclass(frozen=True)
class StopDecision:
    reason: str
    goal_status: str = "satisfied"


class SolverPolicy(Protocol):
    def next_step(self, state: EnvironmentState) -> ActionSpec | StopDecision: ...


@dataclass(frozen=True)
class SolverLoopResult:
    stop_reason: str
    goal_status: str
    actions_executed: int
    actions_succeeded: int
    actions_failed: int
    snapshot_hash: str

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


class StatefulSolverLoop:
    def __init__(
        self,
        session: SolverStateSession,
        executor: ActionExecutor,
        max_actions: int,
        goal_id: str = "environment-ready",
        goal_description: str = "Construct an executable project environment",
    ) -> None:
        if max_actions <= 0:
            raise ValueError("StatefulSolverLoop.max_actions must be positive")
        self.session = session
        self.executor = executor
        self.max_actions = max_actions
        self.goal_id = goal_id
        self.goal_description = goal_description

    def _finish(
        self,
        reason: str,
        goal_status: str,
        executed: int,
        succeeded: int,
        failed: int,
    ) -> SolverLoopResult:
        self.session.upsert_goal(
            self.goal_id,
            self.goal_description,
            goal_status,
        )
        snapshot = self.session.refresh_snapshot()
        return SolverLoopResult(
            stop_reason=reason,
            goal_status=goal_status,
            actions_executed=executed,
            actions_succeeded=succeeded,
            actions_failed=failed,
            snapshot_hash=str(snapshot["snapshot_hash"]),
        )

    def run(self, policy: SolverPolicy) -> SolverLoopResult:
        state = self.session.reconstruct()
        if self.goal_id not in state.goals:
            self.session.upsert_goal(
                self.goal_id,
                self.goal_description,
                "in_progress",
            )
        executed = succeeded = failed = 0
        while executed < self.max_actions:
            try:
                decision = policy.next_step(self.session.reconstruct())
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                self.session.record_failure("policy-exception", message)
                return self._finish(message, "blocked", executed, succeeded, failed)
            if isinstance(decision, StopDecision):
                if decision.goal_status not in {"satisfied", "blocked"}:
                    raise ValueError(
                        "StopDecision.goal_status must be 'satisfied' or 'blocked'"
                    )
                return self._finish(
                    decision.reason,
                    decision.goal_status,
                    executed,
                    succeeded,
                    failed,
                )
            if not isinstance(decision, ActionSpec):
                raise TypeError("Solver policy must return ActionSpec or StopDecision")
            result = self.session.execute_action(decision, self.executor)
            executed += 1
            if result.exit_code == 0:
                succeeded += 1
            else:
                failed += 1
        self.session.record_failure(
            "action-budget",
            f"Solver exhausted the action budget of {self.max_actions}",
        )
        return self._finish(
            "action budget exhausted",
            "blocked",
            executed,
            succeeded,
            failed,
        )
