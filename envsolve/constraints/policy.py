from __future__ import annotations

from envsolve.constraints.engine import ConstraintEngine
from envsolve.constraints.preflight import (
    PreflightDisposition,
    action_mutates_environment,
    preflight_action,
)
from envsolve.solver.loop import SolverPolicy, StopDecision
from envsolve.solver.session import ActionSpec, SolverStateSession
from envsolve.state import EnvironmentState


class ConstraintCheckedPolicy:
    def __init__(
        self,
        inner: SolverPolicy,
        session: SolverStateSession,
        engine: ConstraintEngine | None = None,
    ) -> None:
        self.inner = inner
        self.session = session
        self.engine = engine or ConstraintEngine()

    def next_step(self, state: EnvironmentState) -> ActionSpec | StopDecision:
        report = self.engine.propagate(self.session)
        current = self.session.reconstruct()
        decision = self.inner.next_step(current)
        if isinstance(decision, StopDecision):
            return decision
        if not isinstance(decision, ActionSpec):
            raise TypeError("Solver policy must return ActionSpec or StopDecision")

        preflight = preflight_action(current, decision, self.engine)
        evidence_id = self.session.record_evidence(
            kind="constraint-preflight",
            source="constraint-engine-v1",
            value={
                "action_type": decision.action_type,
                "command": decision.command,
                "result": preflight.to_dict(),
                "solve_report": report.to_dict(),
            },
        )
        if preflight.disposition == PreflightDisposition.ALLOW:
            return decision
        if (
            preflight.disposition == PreflightDisposition.REQUIRE_EVIDENCE
            and not action_mutates_environment(decision)
        ):
            return decision

        reason = "; ".join(preflight.reasons) or preflight.disposition.value
        self.session.record_failure(
            category=f"constraint-preflight-{preflight.disposition.value}",
            message=reason,
            details={
                "evidence_id": evidence_id,
                "constraint_ids": list(preflight.constraint_ids),
                "conflicts": [item.to_dict() for item in preflight.conflicts],
            },
        )
        return StopDecision(reason=reason, goal_status="blocked")
