from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum
import hashlib
import json
from typing import Any, Iterable

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version


CONSTRAINT_SCHEMA_VERSION = "1.0.0"


class ConstraintDomain(str, Enum):
    RUNTIME = "runtime"
    PACKAGE = "package"
    CAPABILITY = "capability"
    MODULE = "module"
    PLATFORM = "platform"


class ConstraintRole(str, Enum):
    REQUIREMENT = "requirement"
    FACT = "fact"


class ConstraintPredicate(str, Enum):
    VERSION = "version"
    PRESENT = "present"
    EQUALS = "equals"


def canonical_subject(domain: ConstraintDomain, subject: str) -> str:
    value = subject.strip()
    if not value:
        raise ValueError("Constraint subject cannot be empty")
    if domain == ConstraintDomain.PACKAGE:
        return canonicalize_name(value)
    if domain in {ConstraintDomain.RUNTIME, ConstraintDomain.PLATFORM}:
        return value.lower()
    return value


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True)
class NormalizedConstraint:
    domain: ConstraintDomain
    subject: str
    predicate: ConstraintPredicate
    value: str | bool
    role: ConstraintRole
    evidence_ids: tuple[str, ...]
    confidence: float = 1.0
    scope_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "subject", canonical_subject(self.domain, self.subject))
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))
        if self.scope_id is not None and not self.scope_id.strip():
            raise ValueError("Constraint scope_id cannot be empty")
        if self.role == ConstraintRole.REQUIREMENT and self.scope_id is not None:
            raise ValueError("Requirements are global and cannot have a candidate scope")
        if isinstance(self.confidence, bool) or not 0 <= self.confidence <= 1:
            raise ValueError("Constraint confidence must be in [0, 1]")
        if self.predicate == ConstraintPredicate.VERSION:
            if not isinstance(self.value, str):
                raise ValueError("Version constraints require a string value")
            try:
                if self.role == ConstraintRole.REQUIREMENT:
                    normalized_version = str(SpecifierSet(self.value))
                else:
                    normalized_version = str(Version(self.value))
            except (InvalidSpecifier, InvalidVersion) as exc:
                raise ValueError(f"Invalid version constraint: {self.value!r}") from exc
            object.__setattr__(self, "value", normalized_version)
        elif self.predicate == ConstraintPredicate.PRESENT:
            if not isinstance(self.value, bool):
                raise ValueError("Presence constraints require a boolean value")
        elif not isinstance(self.value, str):
            raise ValueError("Equality constraints require a string value")

    @property
    def constraint_id(self) -> str:
        digest = hashlib.sha256(self.semantic_json().encode("utf-8")).hexdigest()[:16]
        return f"constraint-{self.domain.value}-{digest}"

    @property
    def state_kind(self) -> str:
        return f"typed:{self.domain.value}:{self.role.value}"

    def semantic_dict(self) -> dict[str, Any]:
        value = {
            "schema_version": CONSTRAINT_SCHEMA_VERSION,
            "domain": self.domain.value,
            "subject": self.subject,
            "predicate": self.predicate.value,
            "value": self.value,
            "role": self.role.value,
        }
        if self.scope_id is not None:
            value["scope_id"] = self.scope_id
        return value

    def semantic_json(self) -> str:
        return _canonical_json(self.semantic_dict())

    def expression_dict(self) -> dict[str, Any]:
        return {**self.semantic_dict(), "confidence": self.confidence}

    def expression_json(self) -> str:
        return _canonical_json(self.expression_dict())

    def with_evidence(
        self,
        evidence_ids: Iterable[str],
        confidence: float | None = None,
    ) -> "NormalizedConstraint":
        return replace(
            self,
            evidence_ids=tuple(sorted(set(self.evidence_ids) | set(evidence_ids))),
            confidence=max(self.confidence, confidence or 0.0),
        )

    def to_state_fields(self, status: str) -> dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "kind": self.state_kind,
            "expression": self.expression_json(),
            "status": status,
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_state_record(cls, record: dict[str, Any]) -> "NormalizedConstraint":
        expression = json.loads(str(record["expression"]))
        if expression.get("schema_version") != CONSTRAINT_SCHEMA_VERSION:
            raise ValueError("Unsupported normalized constraint schema")
        constraint = cls(
            domain=ConstraintDomain(expression["domain"]),
            subject=str(expression["subject"]),
            predicate=ConstraintPredicate(expression["predicate"]),
            value=expression["value"],
            role=ConstraintRole(expression["role"]),
            evidence_ids=tuple(str(item) for item in record.get("evidence_ids", [])),
            confidence=float(expression.get("confidence", 1.0)),
            scope_id=expression.get("scope_id"),
        )
        if record.get("constraint_id") != constraint.constraint_id:
            raise ValueError("Normalized constraint identifier mismatch")
        return constraint

    @classmethod
    def proposed_fact(cls, value: dict[str, Any]) -> "NormalizedConstraint":
        return cls(
            domain=ConstraintDomain(value["domain"]),
            subject=str(value["subject"]),
            predicate=ConstraintPredicate(value["predicate"]),
            value=value["value"],
            role=ConstraintRole.FACT,
            evidence_ids=(),
            confidence=float(value.get("confidence", 1.0)),
        )


@dataclass(frozen=True)
class ConstraintConflict:
    conflict_id: str
    domain: str
    subject: str
    constraint_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def create(
        cls,
        constraints: Iterable[NormalizedConstraint],
        message: str,
    ) -> "ConstraintConflict":
        values = tuple(constraints)
        constraint_ids = tuple(sorted(item.constraint_id for item in values))
        evidence_ids = tuple(
            sorted({evidence for item in values for evidence in item.evidence_ids})
        )
        key = _canonical_json(
            {"constraint_ids": constraint_ids, "message": message}
        )
        return cls(
            conflict_id=f"conflict-{hashlib.sha256(key.encode()).hexdigest()[:16]}",
            domain=values[0].domain.value,
            subject=values[0].subject,
            constraint_ids=constraint_ids,
            evidence_ids=evidence_ids,
            message=message,
        )


@dataclass(frozen=True)
class SolveReport:
    statuses: dict[str, str]
    conflicts: tuple[ConstraintConflict, ...]
    managed_constraints: int
    provisional_constraints: tuple[str, ...] = ()

    @property
    def satisfiable(self) -> bool:
        return not self.conflicts

    def to_dict(self) -> dict[str, Any]:
        return {
            "satisfiable": self.satisfiable,
            "statuses": dict(sorted(self.statuses.items())),
            "conflicts": [item.to_dict() for item in self.conflicts],
            "managed_constraints": self.managed_constraints,
            "provisional_constraints": list(self.provisional_constraints),
        }
