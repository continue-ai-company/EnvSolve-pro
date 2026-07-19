from __future__ import annotations

from envsolve.constraints import ConstraintEngine
from envsolve.operations.models import (
    OperationKind,
    OperationPlan,
    OperationRequirement,
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
    """Project hard conflicts into auditable operation obligations."""

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
                    allowed_operation_kinds=allowed,
                    source_conflict_ids=(conflict.conflict_id,),
                    source_constraint_ids=conflict.constraint_ids,
                )
            )
        return OperationPlan(tuple(requirements), tuple(unsupported))
