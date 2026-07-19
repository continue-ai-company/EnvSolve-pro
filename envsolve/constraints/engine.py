from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Iterable

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from envsolve.constraints.models import (
    ConstraintConflict,
    ConstraintPredicate,
    ConstraintRole,
    NormalizedConstraint,
    SolveReport,
)
from envsolve.constraints.normalization import EvidenceNormalizer
from envsolve.solver.session import SolverStateSession
from envsolve.state import EnvironmentState


@dataclass(frozen=True)
class _VersionBound:
    version: Version
    inclusive: bool


def _max_lower(current: _VersionBound | None, candidate: _VersionBound) -> _VersionBound:
    if current is None or candidate.version > current.version:
        return candidate
    if candidate.version == current.version:
        return _VersionBound(current.version, current.inclusive and candidate.inclusive)
    return current


def _min_upper(current: _VersionBound | None, candidate: _VersionBound) -> _VersionBound:
    if current is None or candidate.version < current.version:
        return candidate
    if candidate.version == current.version:
        return _VersionBound(current.version, current.inclusive and candidate.inclusive)
    return current


def _prefix_bounds(value: str, *, compatible: bool = False) -> tuple[Version, Version]:
    raw = value[:-2] if value.endswith(".*") else value
    version = Version(raw)
    release = list(version.release[:-1] if compatible else version.release)
    if not release:
        raise ValueError(f"Version prefix has no release segment: {value!r}")
    upper_release = list(release)
    upper_release[-1] += 1
    epoch = f"{version.epoch}!" if version.epoch else ""
    return Version(epoch + ".".join(map(str, release))), Version(
        epoch + ".".join(map(str, upper_release))
    )


def _obviously_empty(specifiers: SpecifierSet) -> bool:
    """Detect empty ordered intervals without claiming full PEP 440 SAT solving."""
    lower: _VersionBound | None = None
    upper: _VersionBound | None = None
    for specifier in specifiers:
        operator = specifier.operator
        value = specifier.version
        if operator in {">", ">="}:
            lower = _max_lower(lower, _VersionBound(Version(value), operator == ">="))
        elif operator in {"<", "<="}:
            upper = _min_upper(upper, _VersionBound(Version(value), operator == "<="))
        elif operator == "==" and "*" not in value:
            exact = _VersionBound(Version(value), True)
            lower = _max_lower(lower, exact)
            upper = _min_upper(upper, exact)
        elif operator == "==" and value.endswith(".*"):
            prefix_lower, prefix_upper = _prefix_bounds(value)
            lower = _max_lower(lower, _VersionBound(prefix_lower, True))
            upper = _min_upper(upper, _VersionBound(prefix_upper, False))
        elif operator == "~=":
            compatible_lower = Version(value)
            _, compatible_upper = _prefix_bounds(value, compatible=True)
            lower = _max_lower(lower, _VersionBound(compatible_lower, True))
            upper = _min_upper(upper, _VersionBound(compatible_upper, False))

    if lower is None or upper is None:
        return False
    if lower.version > upper.version:
        return True
    if lower.version < upper.version:
        return False
    if not (lower.inclusive and upper.inclusive):
        return True
    return lower.version not in specifiers


class ConstraintEngine:
    def __init__(
        self,
        normalizer: EvidenceNormalizer | None = None,
        hard_confidence: float = 0.8,
    ) -> None:
        if isinstance(hard_confidence, bool) or not 0 <= hard_confidence <= 1:
            raise ValueError("hard_confidence must be in [0, 1]")
        self.normalizer = normalizer or EvidenceNormalizer()
        self.hard_confidence = hard_confidence

    @staticmethod
    def typed_constraints(state: EnvironmentState) -> tuple[NormalizedConstraint, ...]:
        constraints: list[NormalizedConstraint] = []
        for record in state.constraints.values():
            if not str(record.get("kind", "")).startswith("typed:"):
                continue
            if record.get("status") == "superseded":
                continue
            constraints.append(NormalizedConstraint.from_state_record(record))
        return tuple(sorted(constraints, key=lambda item: item.constraint_id))

    def ingest_evidence(
        self,
        session: SolverStateSession,
        evidence_id: str,
        *,
        fact_scope: str | None = None,
    ) -> tuple[str, ...]:
        state = session.reconstruct()
        evidence = state.evidence.get(evidence_id)
        if evidence is None:
            raise ValueError(f"Unknown evidence identifier: {evidence_id}")
        normalized = tuple(
            replace(item, scope_id=fact_scope)
            if item.role == ConstraintRole.FACT and fact_scope is not None
            else item
            for item in self.normalizer.normalize(evidence_id, evidence)
        )
        changed: list[str] = []
        for candidate in normalized:
            current_record = state.constraints.get(candidate.constraint_id)
            current: NormalizedConstraint | None = None
            status = "active"
            if current_record is not None:
                if not str(current_record.get("kind", "")).startswith("typed:"):
                    raise ValueError(
                        f"Constraint identifier collision: {candidate.constraint_id}"
                    )
                current = NormalizedConstraint.from_state_record(current_record)
                status = str(current_record["status"])
                candidate = current.with_evidence(
                    candidate.evidence_ids,
                    candidate.confidence,
                )
            fields = candidate.to_state_fields(status)
            if current_record is not None and all(
                current_record.get(key) == value
                for key, value in fields.items()
            ):
                continue
            session.upsert_constraint(
                fields["constraint_id"],
                fields["kind"],
                fields["expression"],
                fields["status"],
                fields["evidence_ids"],
            )
            changed.append(candidate.constraint_id)
            state = session.reconstruct()
        return tuple(changed)

    def supersede_active_facts(self, session: SolverStateSession) -> tuple[str, ...]:
        """Retire observations from the previous candidate's environment view."""
        return self.supersede_facts(
            session,
            tuple(
                item.constraint_id
                for item in self.typed_constraints(session.reconstruct())
                if item.role == ConstraintRole.FACT
            ),
        )

    @classmethod
    def fact_constraint_ids(
        cls,
        state: EnvironmentState,
        constraint_ids: Iterable[str] | None = None,
    ) -> tuple[str, ...]:
        selected = set(constraint_ids) if constraint_ids is not None else None
        return tuple(
            item.constraint_id
            for item in cls.typed_constraints(state)
            if item.role == ConstraintRole.FACT
            and (selected is None or item.constraint_id in selected)
        )

    def supersede_facts(
        self,
        session: SolverStateSession,
        constraint_ids: Iterable[str],
    ) -> tuple[str, ...]:
        state = session.reconstruct()
        changed: list[str] = []
        for constraint_id in sorted(set(constraint_ids)):
            record = state.constraints.get(constraint_id)
            if record is None or record.get("status") == "superseded":
                continue
            item = NormalizedConstraint.from_state_record(record)
            if item.role != ConstraintRole.FACT:
                raise ValueError("Only fact constraints may be superseded as observations")
            session.upsert_constraint(
                item.constraint_id,
                str(record["kind"]),
                str(record["expression"]),
                "superseded",
                list(record["evidence_ids"]),
            )
            changed.append(item.constraint_id)
        return tuple(changed)

    def supersede_replaced_facts(
        self,
        session: SolverStateSession,
        prior_fact_ids: Iterable[str],
        replacement_fact_ids: Iterable[str],
    ) -> tuple[str, ...]:
        """Retire only prior observations of variables observed by a new candidate."""
        state = session.reconstruct()
        replacement_ids = set(replacement_fact_ids)
        replacement_keys = set()
        for constraint_id in replacement_ids:
            record = state.constraints.get(constraint_id)
            if record is None:
                continue
            item = NormalizedConstraint.from_state_record(record)
            if item.role == ConstraintRole.FACT:
                replacement_keys.add((item.domain, item.subject, item.predicate))

        replaced: list[str] = []
        for constraint_id in prior_fact_ids:
            record = state.constraints.get(constraint_id)
            if record is None:
                continue
            item = NormalizedConstraint.from_state_record(record)
            if (
                item.role == ConstraintRole.FACT
                and constraint_id not in replacement_ids
                and (item.domain, item.subject, item.predicate) in replacement_keys
            ):
                replaced.append(constraint_id)
        return self.supersede_facts(session, replaced)

    def ingest_all(self, session: SolverStateSession) -> tuple[str, ...]:
        changed: list[str] = []
        for evidence_id in sorted(session.reconstruct().evidence):
            changed.extend(self.ingest_evidence(session, evidence_id))
        return tuple(changed)

    def solve_state(self, state: EnvironmentState) -> SolveReport:
        return self.solve(self.typed_constraints(state))

    def solve(
        self,
        constraints: Iterable[NormalizedConstraint],
    ) -> SolveReport:
        values = tuple(constraints)
        statuses: dict[str, str] = {}
        hard: list[NormalizedConstraint] = []
        provisional: list[str] = []
        for item in values:
            if item.confidence < self.hard_confidence:
                statuses[item.constraint_id] = "active"
                provisional.append(item.constraint_id)
                continue
            hard.append(item)
            statuses[item.constraint_id] = (
                "active"
                if item.role == ConstraintRole.REQUIREMENT
                else "satisfied"
            )

        grouped: dict[
            tuple[str, str, str], list[NormalizedConstraint]
        ] = defaultdict(list)
        for item in hard:
            grouped[(item.domain.value, item.subject, item.predicate.value)].append(item)

        conflicts: list[ConstraintConflict] = []
        for group in grouped.values():
            if group[0].predicate == ConstraintPredicate.VERSION:
                group_conflicts = self._solve_versions(group, statuses)
            else:
                group_conflicts = self._solve_discrete(group, statuses)
            conflicts.extend(group_conflicts)

        unique_conflicts = {
            conflict.conflict_id: conflict for conflict in conflicts
        }
        ordered_conflicts = tuple(
            unique_conflicts[key] for key in sorted(unique_conflicts)
        )
        return SolveReport(
            statuses=dict(sorted(statuses.items())),
            conflicts=ordered_conflicts,
            managed_constraints=len(values),
            provisional_constraints=tuple(sorted(provisional)),
        )

    @staticmethod
    def _mark_conflict(
        constraints: Iterable[NormalizedConstraint],
        statuses: dict[str, str],
        message: str,
    ) -> ConstraintConflict:
        values = tuple(constraints)
        for item in values:
            statuses[item.constraint_id] = "violated"
        return ConstraintConflict.create(values, message)

    def _solve_versions(
        self,
        group: list[NormalizedConstraint],
        statuses: dict[str, str],
    ) -> list[ConstraintConflict]:
        requirements = [item for item in group if item.role == ConstraintRole.REQUIREMENT]
        facts = [item for item in group if item.role == ConstraintRole.FACT]
        conflicts: list[ConstraintConflict] = []
        fact_versions = {Version(str(item.value)) for item in facts}
        if len(fact_versions) > 1:
            conflicts.append(
                self._mark_conflict(
                    facts,
                    statuses,
                    f"Conflicting observed versions for {group[0].subject}",
                )
            )
            return conflicts

        combined = SpecifierSet(",".join(str(item.value) for item in requirements))
        if facts:
            fact = facts[0]
            if requirements and Version(str(fact.value)) not in combined:
                conflicts.append(
                    self._mark_conflict(
                        [*requirements, *facts],
                        statuses,
                        f"Observed {group[0].subject} version {fact.value} does not "
                        f"satisfy {combined}",
                    )
                )
            else:
                for requirement in requirements:
                    statuses[requirement.constraint_id] = "satisfied"
            return conflicts

        if requirements and _obviously_empty(combined):
            conflicts.append(
                self._mark_conflict(
                    requirements,
                    statuses,
                    f"No {group[0].subject} version satisfies {combined}",
                )
            )
            return conflicts

        exact_versions: set[Version] = set()
        for requirement in requirements:
            for specifier in SpecifierSet(str(requirement.value)):
                if specifier.operator == "==" and "*" not in specifier.version:
                    exact_versions.add(Version(specifier.version))
        if exact_versions and not any(version in combined for version in exact_versions):
            conflicts.append(
                self._mark_conflict(
                    requirements,
                    statuses,
                    f"No exact {group[0].subject} version satisfies {combined}",
                )
            )
        return conflicts

    def _solve_discrete(
        self,
        group: list[NormalizedConstraint],
        statuses: dict[str, str],
    ) -> list[ConstraintConflict]:
        requirements = [item for item in group if item.role == ConstraintRole.REQUIREMENT]
        facts = [item for item in group if item.role == ConstraintRole.FACT]
        conflicts: list[ConstraintConflict] = []
        requirement_values = {item.value for item in requirements}
        fact_values = {item.value for item in facts}
        if len(requirement_values) > 1:
            conflicts.append(
                self._mark_conflict(
                    requirements,
                    statuses,
                    f"Conflicting requirements for {group[0].subject}",
                )
            )
        if len(fact_values) > 1:
            conflicts.append(
                self._mark_conflict(
                    facts,
                    statuses,
                    f"Conflicting observed values for {group[0].subject}",
                )
            )
        if (
            len(requirement_values) == 1
            and len(fact_values) == 1
            and requirement_values != fact_values
        ):
            conflicts.append(
                self._mark_conflict(
                    [*requirements, *facts],
                    statuses,
                    f"Observed {group[0].subject} value does not satisfy its requirement",
                )
            )
        elif requirement_values and requirement_values == fact_values:
            for requirement in requirements:
                statuses[requirement.constraint_id] = "satisfied"
        return conflicts

    def propagate_constraints(self, session: SolverStateSession) -> SolveReport:
        """Solve and persist constraints already admitted into state."""
        state = session.reconstruct()
        report = self.solve_state(state)
        for item in self.typed_constraints(state):
            record = state.constraints[item.constraint_id]
            status = report.statuses[item.constraint_id]
            if record["status"] == status:
                continue
            fields = item.to_state_fields(status)
            session.upsert_constraint(
                fields["constraint_id"],
                fields["kind"],
                fields["expression"],
                fields["status"],
                fields["evidence_ids"],
            )
        return report

    def propagate(self, session: SolverStateSession) -> SolveReport:
        self.ingest_all(session)
        return self.propagate_constraints(session)
