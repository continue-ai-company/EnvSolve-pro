from __future__ import annotations

from dataclasses import dataclass
import re
import shlex
from typing import Protocol

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from envsolve.constraints import (
    ConstraintConflict,
    ConstraintDomain,
    ConstraintPredicate,
    ConstraintRole,
    NormalizedConstraint,
    SolveReport,
)
from envsolve.repairs.engine import RepairConstraintEngine
from envsolve.repairs.models import (
    ProbeKind,
    RepairContext,
    RepairKind,
    RepairPlan,
    RepairRisk,
    VerificationProbe,
)
from envsolve.state import EnvironmentState


SAFE_CAPABILITY = re.compile(r"^[A-Za-z0-9_.+-]+$")
SAFE_SYSTEM_PACKAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+._:@/-]*$")
SAFE_MODULE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")


class RepairOperator(Protocol):
    kind: RepairKind

    def matches(self, conflict: ConstraintConflict) -> bool: ...

    def missing_context(
        self,
        conflict: ConstraintConflict,
        context: RepairContext,
    ) -> tuple[str, ...]: ...

    def propose(
        self,
        conflict: ConstraintConflict,
        constraints: dict[str, NormalizedConstraint],
        context: RepairContext,
    ) -> tuple[RepairPlan, ...]: ...


def _members(
    conflict: ConstraintConflict,
    constraints: dict[str, NormalizedConstraint],
) -> tuple[NormalizedConstraint, ...]:
    return tuple(
        constraints[constraint_id]
        for constraint_id in conflict.constraint_ids
        if constraint_id in constraints
    )


def _base_plan_fields(
    conflict: ConstraintConflict,
    members: tuple[NormalizedConstraint, ...],
    context: RepairContext,
) -> dict[str, tuple[str, ...]]:
    return {
        "source_conflict_ids": (conflict.conflict_id,),
        "source_constraint_ids": tuple(item.constraint_id for item in members),
        "supersede_constraint_ids": tuple(
            item.constraint_id for item in members if item.role == ConstraintRole.FACT
        ),
        "supporting_evidence_ids": context.evidence_ids,
    }


@dataclass(frozen=True)
class RuntimeSelectionOperator:
    kind = RepairKind.RUNTIME_SELECTION

    def matches(self, conflict: ConstraintConflict) -> bool:
        return (
            conflict.domain == ConstraintDomain.RUNTIME.value
            and conflict.subject == "python"
        )

    def missing_context(
        self,
        conflict: ConstraintConflict,
        context: RepairContext,
    ) -> tuple[str, ...]:
        if not self.matches(conflict):
            return ()
        missing: list[str] = []
        if context.runtime_manager != "pyenv":
            missing.append("runtime_manager:pyenv")
        if not context.available_python_versions:
            missing.append("available_python_versions")
        if not context.evidence_ids:
            missing.append("evidence_ids")
        return tuple(missing)

    def propose(
        self,
        conflict: ConstraintConflict,
        constraints: dict[str, NormalizedConstraint],
        context: RepairContext,
    ) -> tuple[RepairPlan, ...]:
        if (
            not self.matches(conflict)
            or context.runtime_manager != "pyenv"
            or not context.evidence_ids
        ):
            return ()
        members = _members(conflict, constraints)
        requirements = [
            item
            for item in members
            if item.role == ConstraintRole.REQUIREMENT
            and item.predicate == ConstraintPredicate.VERSION
        ]
        facts = [
            item
            for item in members
            if item.role == ConstraintRole.FACT
            and item.predicate == ConstraintPredicate.VERSION
        ]
        if not requirements or not facts:
            return ()
        specifier = SpecifierSet(",".join(str(item.value) for item in requirements))
        candidates = [
            Version(value)
            for value in context.available_python_versions
            if Version(value) in specifier
        ]
        if not candidates:
            return ()
        target = str(max(candidates))
        fact = NormalizedConstraint(
            ConstraintDomain.RUNTIME,
            "python",
            ConstraintPredicate.VERSION,
            target,
            ConstraintRole.FACT,
            (),
        )
        return (
            RepairPlan(
                kind=RepairKind.RUNTIME_SELECTION,
                proposed_fact=fact,
                mutation_action_type="runtime_configure",
                mutation_command=f"pyenv local {shlex.quote(target)} && hash -r",
                rationale=f"Select observed compatible Python {target}",
                risk=RepairRisk.MODERATE,
                probe=VerificationProbe(
                    ProbeKind.RUNTIME_VERSION,
                    "python --version",
                    fact,
                ),
                **_base_plan_fields(conflict, members, context),
            ),
        )


def _system_install_command(manager: str, package: str) -> str:
    if not SAFE_SYSTEM_PACKAGE.fullmatch(package):
        raise ValueError(f"Unsafe system package candidate: {package!r}")
    quoted = shlex.quote(package)
    if manager in {"apt", "apt-get"}:
        return f"{manager} install -y -- {quoted}"
    if manager == "apk":
        return f"apk add -- {quoted}"
    if manager == "brew":
        return f"brew install {quoted}"
    if manager in {"dnf", "yum"}:
        return f"{manager} install -y -- {quoted}"
    raise ValueError(f"Unsupported system package manager: {manager}")


@dataclass(frozen=True)
class SystemCapabilityInstallOperator:
    kind = RepairKind.SYSTEM_CAPABILITY_INSTALL

    def matches(self, conflict: ConstraintConflict) -> bool:
        return conflict.domain == ConstraintDomain.CAPABILITY.value

    def missing_context(
        self,
        conflict: ConstraintConflict,
        context: RepairContext,
    ) -> tuple[str, ...]:
        if not self.matches(conflict):
            return ()
        missing: list[str] = []
        if context.system_package_manager is None:
            missing.append("system_package_manager")
        if not (context.capability_packages or {}).get(conflict.subject):
            missing.append(f"capability_packages:{conflict.subject}")
        if not context.evidence_ids:
            missing.append("evidence_ids")
        return tuple(missing)

    def propose(
        self,
        conflict: ConstraintConflict,
        constraints: dict[str, NormalizedConstraint],
        context: RepairContext,
    ) -> tuple[RepairPlan, ...]:
        if (
            not self.matches(conflict)
            or context.system_package_manager is None
            or not SAFE_CAPABILITY.fullmatch(conflict.subject)
            or not context.evidence_ids
        ):
            return ()
        members = _members(conflict, constraints)
        required = any(
            item.role == ConstraintRole.REQUIREMENT
            and item.predicate == ConstraintPredicate.PRESENT
            and item.value is True
            for item in members
        )
        absent = any(
            item.role == ConstraintRole.FACT
            and item.predicate == ConstraintPredicate.PRESENT
            and item.value is False
            for item in members
        )
        if not required or not absent:
            return ()
        packages = (context.capability_packages or {}).get(conflict.subject, ())
        plans: list[RepairPlan] = []
        for package in packages:
            fact = NormalizedConstraint(
                ConstraintDomain.CAPABILITY,
                conflict.subject,
                ConstraintPredicate.PRESENT,
                True,
                ConstraintRole.FACT,
                (),
            )
            plans.append(
                RepairPlan(
                    kind=RepairKind.SYSTEM_CAPABILITY_INSTALL,
                    proposed_fact=fact,
                    mutation_action_type="system_package_install",
                    mutation_command=_system_install_command(
                        context.system_package_manager,
                        package,
                    ),
                    rationale=(
                        f"Install context-provided package {package} for "
                        f"capability {conflict.subject}"
                    ),
                    risk=RepairRisk.HIGH,
                    probe=VerificationProbe(
                        ProbeKind.CAPABILITY_PRESENCE,
                        f"command -v -- {shlex.quote(conflict.subject)}",
                        fact,
                    ),
                    **_base_plan_fields(conflict, members, context),
                )
            )
        return tuple(plans)


@dataclass(frozen=True)
class PythonModuleInstallOperator:
    kind = RepairKind.PYTHON_MODULE_INSTALL

    def matches(self, conflict: ConstraintConflict) -> bool:
        return conflict.domain == ConstraintDomain.MODULE.value

    def missing_context(
        self,
        conflict: ConstraintConflict,
        context: RepairContext,
    ) -> tuple[str, ...]:
        if not self.matches(conflict):
            return ()
        missing: list[str] = []
        if not (context.module_distributions or {}).get(conflict.subject):
            missing.append(f"module_distributions:{conflict.subject}")
        if not context.evidence_ids:
            missing.append("evidence_ids")
        return tuple(missing)

    def propose(
        self,
        conflict: ConstraintConflict,
        constraints: dict[str, NormalizedConstraint],
        context: RepairContext,
    ) -> tuple[RepairPlan, ...]:
        if (
            not self.matches(conflict)
            or not SAFE_MODULE.fullmatch(conflict.subject)
            or not context.evidence_ids
        ):
            return ()
        members = _members(conflict, constraints)
        required = any(
            item.role == ConstraintRole.REQUIREMENT
            and item.predicate == ConstraintPredicate.PRESENT
            and item.value is True
            for item in members
        )
        absent = any(
            item.role == ConstraintRole.FACT
            and item.predicate == ConstraintPredicate.PRESENT
            and item.value is False
            for item in members
        )
        if not required or not absent:
            return ()
        distributions = (context.module_distributions or {}).get(conflict.subject, ())
        plans: list[RepairPlan] = []
        for distribution in distributions:
            try:
                Requirement(distribution)
            except InvalidRequirement as exc:
                raise ValueError(
                    f"Invalid Python distribution candidate: {distribution!r}"
                ) from exc
            fact = NormalizedConstraint(
                ConstraintDomain.MODULE,
                conflict.subject,
                ConstraintPredicate.PRESENT,
                True,
                ConstraintRole.FACT,
                (),
            )
            import_source = f"import {conflict.subject}"
            plans.append(
                RepairPlan(
                    kind=RepairKind.PYTHON_MODULE_INSTALL,
                    proposed_fact=fact,
                    mutation_action_type="python_package_install",
                    mutation_command=(
                        f"python -m pip install {shlex.quote(distribution)}"
                    ),
                    rationale=(
                        f"Install context-provided distribution {distribution} "
                        f"for module {conflict.subject}"
                    ),
                    risk=RepairRisk.LOW,
                    probe=VerificationProbe(
                        ProbeKind.MODULE_PRESENCE,
                        f"python -c {shlex.quote(import_source)}",
                        fact,
                    ),
                    **_base_plan_fields(conflict, members, context),
                )
            )
        return tuple(plans)


class RepairRegistry:
    def __init__(self, operators: tuple[RepairOperator, ...] | None = None) -> None:
        self.operators = operators or (
            RuntimeSelectionOperator(),
            PythonModuleInstallOperator(),
            SystemCapabilityInstallOperator(),
        )

    def propose(
        self,
        state: EnvironmentState,
        context: RepairContext,
        engine: RepairConstraintEngine | None = None,
    ) -> tuple[RepairPlan, ...]:
        active_engine = engine or RepairConstraintEngine()
        report: SolveReport = active_engine.solve_state(state)
        constraints = {
            item.constraint_id: item
            for item in active_engine.typed_constraints(state)
        }
        plans: dict[str, RepairPlan] = {}
        for conflict in report.conflicts:
            for operator in self.operators:
                for plan in operator.propose(conflict, constraints, context):
                    plans[plan.repair_id] = plan
        risk_order = {
            RepairRisk.LOW: 0,
            RepairRisk.MODERATE: 1,
            RepairRisk.HIGH: 2,
        }
        return tuple(
            sorted(
                plans.values(),
                key=lambda item: (risk_order[item.risk], item.repair_id),
            )
        )

    def coverage(
        self,
        state: EnvironmentState,
        context: RepairContext,
        engine: RepairConstraintEngine | None = None,
    ) -> tuple[dict[str, object], ...]:
        active_engine = engine or RepairConstraintEngine()
        report = active_engine.solve_state(state)
        rows: list[dict[str, object]] = []
        for conflict in report.conflicts:
            matching = tuple(
                operator for operator in self.operators if operator.matches(conflict)
            )
            missing = sorted(
                {
                    item
                    for operator in matching
                    for item in operator.missing_context(conflict, context)
                }
            )
            rows.append(
                {
                    "conflict_id": conflict.conflict_id,
                    "domain": conflict.domain,
                    "subject": conflict.subject,
                    "operator_kinds": sorted(
                        operator.kind.value for operator in matching
                    ),
                    "missing_context": missing,
                }
            )
        return tuple(rows)
