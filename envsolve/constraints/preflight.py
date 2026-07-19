from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from envsolve.constraints.engine import ConstraintEngine
from envsolve.constraints.models import ConstraintConflict, NormalizedConstraint
from envsolve.solver.session import ActionSpec
from envsolve.state import EnvironmentState


class PreflightDisposition(str, Enum):
    ALLOW = "allow"
    REQUIRE_EVIDENCE = "require_evidence"
    REJECT = "reject"


@dataclass(frozen=True)
class PreflightResult:
    disposition: PreflightDisposition
    reasons: tuple[str, ...]
    constraint_ids: tuple[str, ...]
    conflicts: tuple[ConstraintConflict, ...]
    proposed_facts: int

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["disposition"] = self.disposition.value
        return value


READ_ONLY_ACTION_TYPES = {
    "observation",
    "probe",
    "provider-probe",
    "read_only",
    "verification",
    "verify",
}


def action_mutates_environment(action: ActionSpec) -> bool:
    declared = action.metadata.get("mutates_environment")
    if declared is not None:
        if not isinstance(declared, bool):
            raise ValueError("Action metadata mutates_environment must be boolean")
        return declared
    return action.action_type.strip().lower() not in READ_ONLY_ACTION_TYPES


def preflight_action(
    state: EnvironmentState,
    action: ActionSpec,
    engine: ConstraintEngine,
) -> PreflightResult:
    reasons: list[str] = []
    related_ids: set[str] = set()
    current_report = engine.solve_state(state)
    try:
        mutates = action_mutates_environment(action)
    except ValueError as exc:
        return PreflightResult(
            disposition=PreflightDisposition.REJECT,
            reasons=(str(exc),),
            constraint_ids=(),
            conflicts=(),
            proposed_facts=0,
        )

    unknown = sorted(set(action.preconditions) - state.constraints.keys())
    if unknown:
        reasons.append(f"Unknown preconditions: {', '.join(unknown)}")
        related_ids.update(unknown)

    active: list[str] = []
    violated: list[str] = []
    for constraint_id in action.preconditions:
        status = current_report.statuses.get(
            constraint_id,
            state.constraints.get(constraint_id, {}).get("status"),
        )
        if status == "active":
            active.append(constraint_id)
        elif status == "violated":
            violated.append(constraint_id)
    if violated:
        reasons.append(f"Violated preconditions: {', '.join(sorted(violated))}")
        related_ids.update(violated)
    if active:
        reasons.append(f"Unresolved preconditions: {', '.join(sorted(active))}")
        related_ids.update(active)

    proposed_raw = action.metadata.get("proposed_facts", [])
    if not isinstance(proposed_raw, list):
        return PreflightResult(
            disposition=PreflightDisposition.REJECT,
            reasons=("Action metadata proposed_facts must be a list",),
            constraint_ids=tuple(sorted(related_ids)),
            conflicts=(),
            proposed_facts=0,
        )
    try:
        proposed = tuple(
            NormalizedConstraint.proposed_fact(item) for item in proposed_raw
        )
    except (KeyError, TypeError, ValueError) as exc:
        return PreflightResult(
            disposition=PreflightDisposition.REJECT,
            reasons=(f"Invalid proposed fact: {exc}",),
            constraint_ids=tuple(sorted(related_ids)),
            conflicts=(),
            proposed_facts=0,
        )
    proposed_report = engine.solve([*engine.typed_constraints(state), *proposed])
    new_conflicts = tuple(
        conflict
        for conflict in proposed_report.conflicts
        if conflict.conflict_id
        not in {item.conflict_id for item in current_report.conflicts}
    )
    if new_conflicts:
        reasons.append("Proposed effects conflict with active constraints")
        related_ids.update(
            constraint_id
            for conflict in new_conflicts
            for constraint_id in conflict.constraint_ids
        )
    if mutates and current_report.conflicts:
        reasons.append("Environment has unresolved hard constraint conflicts")
        related_ids.update(
            constraint_id
            for conflict in current_report.conflicts
            for constraint_id in conflict.constraint_ids
        )
    if mutates and not proposed:
        reasons.append("Mutating action does not declare proposed_facts")
    provisional_proposed = sorted(
        item.constraint_id
        for item in proposed
        if item.confidence < engine.hard_confidence
    )
    if provisional_proposed:
        reasons.append(
            "Proposed effects are below the hard-confidence threshold: "
            + ", ".join(provisional_proposed)
        )
        related_ids.update(provisional_proposed)

    reject = bool(unknown or violated or new_conflicts)
    if mutates and current_report.conflicts:
        reject = True
    if reject:
        disposition = PreflightDisposition.REJECT
    elif active or provisional_proposed or (mutates and not proposed):
        disposition = PreflightDisposition.REQUIRE_EVIDENCE
    else:
        disposition = PreflightDisposition.ALLOW
    return PreflightResult(
        disposition=disposition,
        reasons=tuple(reasons),
        constraint_ids=tuple(sorted(related_ids)),
        conflicts=tuple(sorted(new_conflicts, key=lambda item: item.conflict_id)),
        proposed_facts=len(proposed),
    )
