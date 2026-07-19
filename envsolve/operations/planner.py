from __future__ import annotations

from envsolve.constraints import ConstraintEngine
from envsolve.constraints.models import ConstraintRole
from envsolve.operations.models import (
    OperationKind,
    OperationPlan,
    OperationRequirement,
    OperationTrigger,
)
from envsolve.state import EnvironmentState


DOMAIN_OPERATIONS: dict[str, tuple[OperationKind, ...]] = {
    "runtime": (OperationKind.RUNTIME_CONFIGURE,),
    "package": (OperationKind.PYTHON_PACKAGE_INSTALL,),
    "capability": (OperationKind.SYSTEM_PACKAGE_INSTALL,),
    "module": (
        OperationKind.PYTHON_PACKAGE_INSTALL,
        OperationKind.SYSTEM_PACKAGE_INSTALL,
    ),
}


class ConstraintOperationPlanner:
    """Project conflicts and unresolved hard requirements into operations."""

    def __init__(self, constraint_engine: ConstraintEngine | None = None) -> None:
        self.constraint_engine = constraint_engine or ConstraintEngine()

    def plan(self, state: EnvironmentState) -> OperationPlan:
        report = self.constraint_engine.solve_state(state)
        requirements: list[OperationRequirement] = []
        unsupported: list[str] = []
        for conflict in report.conflicts:
            allowed = DOMAIN_OPERATIONS.get(conflict.domain)
            if allowed is None:
                unsupported.append(conflict.conflict_id)
                continue
            requirements.append(
                OperationRequirement(
                    domain=conflict.domain,
                    subject=conflict.subject,
                    trigger=OperationTrigger.CONFLICT,
                    allowed_operation_kinds=allowed,
                    source_conflict_ids=(conflict.conflict_id,),
                    source_constraint_ids=conflict.constraint_ids,
                )
            )
        conflict_constraint_ids = {
            constraint_id
            for conflict in report.conflicts
            for constraint_id in conflict.constraint_ids
        }
        for constraint in self.constraint_engine.typed_constraints(state):
            if (
                constraint.role is not ConstraintRole.REQUIREMENT
                or constraint.constraint_id in conflict_constraint_ids
                or report.statuses.get(constraint.constraint_id) != "active"
                or constraint.confidence < self.constraint_engine.hard_confidence
            ):
                continue
            domain = constraint.domain.value
            allowed = DOMAIN_OPERATIONS.get(domain)
            if allowed is None:
                unsupported.append(constraint.constraint_id)
                continue
            requirements.append(
                OperationRequirement(
                    domain=domain,
                    subject=constraint.subject,
                    trigger=OperationTrigger.UNRESOLVED_REQUIREMENT,
                    allowed_operation_kinds=allowed,
                    source_conflict_ids=(),
                    source_constraint_ids=(constraint.constraint_id,),
                )
            )
        return OperationPlan(tuple(requirements), tuple(unsupported))
