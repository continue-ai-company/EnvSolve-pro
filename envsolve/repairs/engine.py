from __future__ import annotations

from dataclasses import dataclass

from envsolve.constraints import (
    ConstraintEngine,
    ConstraintRole,
    NormalizedConstraint,
    SolveReport,
)
from envsolve.repairs.models import RepairPlan
from envsolve.state import EnvironmentState


class RepairConstraintEngine(ConstraintEngine):
    """Repair-specific name retained for API compatibility."""


@dataclass(frozen=True)
class RepairPreflightResult:
    allowed: bool
    reasons: tuple[str, ...]
    current_report: SolveReport
    projected_report: SolveReport

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "current_report": self.current_report.to_dict(),
            "projected_report": self.projected_report.to_dict(),
        }


def preflight_repair(
    state: EnvironmentState,
    plan: RepairPlan,
    engine: RepairConstraintEngine,
) -> RepairPreflightResult:
    current = engine.solve_state(state)
    reasons: list[str] = []
    active_conflicts = {item.conflict_id: item for item in current.conflicts}
    unknown_conflicts = set(plan.source_conflict_ids) - active_conflicts.keys()
    if unknown_conflicts:
        reasons.append(
            "Unknown or inactive source conflicts: "
            + ", ".join(sorted(unknown_conflicts))
        )
    declared_constraint_ids = {
        constraint_id
        for conflict_id in plan.source_conflict_ids
        if conflict_id in active_conflicts
        for constraint_id in active_conflicts[conflict_id].constraint_ids
    }
    if not set(plan.source_constraint_ids).issubset(declared_constraint_ids):
        reasons.append("Source constraint IDs are not contained in source conflicts")

    unknown_evidence = set(plan.supporting_evidence_ids) - state.evidence.keys()
    if unknown_evidence:
        reasons.append(
            "Unknown supporting evidence: " + ", ".join(sorted(unknown_evidence))
        )
    unknown_prerequisites = set(plan.prerequisite_constraint_ids) - state.constraints.keys()
    if unknown_prerequisites:
        reasons.append(
            "Unknown prerequisite constraints: "
            + ", ".join(sorted(unknown_prerequisites))
        )
    unsatisfied_prerequisites = sorted(
        constraint_id
        for constraint_id in plan.prerequisite_constraint_ids
        if constraint_id in state.constraints
        and current.statuses.get(
            constraint_id,
            state.constraints[constraint_id].get("status"),
        )
        != "satisfied"
    )
    if unsatisfied_prerequisites:
        reasons.append(
            "Unsatisfied prerequisite constraints: "
            + ", ".join(unsatisfied_prerequisites)
        )

    proposed = plan.proposed_fact
    if proposed.confidence < engine.hard_confidence:
        reasons.append("Proposed repair fact is below the hard-confidence threshold")
    active_constraints = {
        item.constraint_id: item for item in engine.typed_constraints(state)
    }
    replacements: list[NormalizedConstraint] = []
    for constraint_id in plan.supersede_constraint_ids:
        item = active_constraints.get(constraint_id)
        if item is None:
            reasons.append(f"Unknown or inactive replacement fact: {constraint_id}")
            continue
        replacements.append(item)
        if item.role != ConstraintRole.FACT:
            reasons.append(f"Repair cannot supersede a requirement: {constraint_id}")
        if item.confidence < engine.hard_confidence:
            reasons.append(f"Repair cannot supersede a provisional fact: {constraint_id}")
        if constraint_id not in declared_constraint_ids:
            reasons.append(f"Replacement fact is outside source conflict: {constraint_id}")
        if (item.domain, item.subject, item.predicate) != (
            proposed.domain,
            proposed.subject,
            proposed.predicate,
        ):
            reasons.append(f"Replacement fact has a different semantic key: {constraint_id}")

    projected_constraints = [
        item
        for item in active_constraints.values()
        if item.constraint_id not in plan.supersede_constraint_ids
    ]
    projected = engine.solve([*projected_constraints, proposed])
    if not projected.satisfiable:
        reasons.append("Projected post-repair state still contains hard conflicts")
    if projected.statuses.get(proposed.constraint_id) != "satisfied":
        reasons.append("Proposed repair fact is not satisfied in projected state")
    return RepairPreflightResult(
        allowed=not reasons,
        reasons=tuple(reasons),
        current_report=current,
        projected_report=projected,
    )
