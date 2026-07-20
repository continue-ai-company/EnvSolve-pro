from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from typing import Any


OPERATION_PLAN_SCHEMA_VERSION = "3.0.0"
OPERATION_FEASIBILITY_SCHEMA_VERSION = "1.0.0"


class OperationKind(str, Enum):
    PYTHON_PACKAGE_INSTALL = "python_package_install"
    SYSTEM_PACKAGE_INSTALL = "system_package_install"
    RUNTIME_CONFIGURE = "runtime_configure"


class OperationFailureClass(str, Enum):
    PYTHON_PROVIDER_TARGET_UNAVAILABLE = "python_provider_target_unavailable"
    SYSTEM_PROVIDER_TARGET_UNAVAILABLE = "system_provider_target_unavailable"


class OperationTrigger(str, Enum):
    CONFLICT = "conflict"
    UNRESOLVED_REQUIREMENT = "unresolved_requirement"
    PRESERVE_SATISFACTION = "preserve_satisfaction"


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def operation_feasibility_subject(
    command: str,
    failure_class: OperationFailureClass | str,
) -> str:
    normalized_command = command.strip()
    if not normalized_command:
        raise ValueError("Operation feasibility command cannot be empty")
    normalized_class = OperationFailureClass(failure_class).value
    return _canonical_json(
        {
            "schema_version": OPERATION_FEASIBILITY_SCHEMA_VERSION,
            "command": normalized_command,
            "failure_class": normalized_class,
        }
    )


def parse_operation_feasibility_subject(subject: str) -> dict[str, str]:
    try:
        value = json.loads(subject)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed operation feasibility subject") from exc
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "command",
        "failure_class",
    }:
        raise ValueError("Malformed operation feasibility subject")
    if value.get("schema_version") != OPERATION_FEASIBILITY_SCHEMA_VERSION:
        raise ValueError("Unsupported operation feasibility schema")
    command = value.get("command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError("Operation feasibility command cannot be empty")
    failure_class = OperationFailureClass(value.get("failure_class")).value
    return {"command": command.strip(), "failure_class": failure_class}


@dataclass(frozen=True)
class OperationRequirement:
    domain: str
    subject: str
    trigger: OperationTrigger
    allowed_operation_kinds: tuple[OperationKind, ...]
    source_conflict_ids: tuple[str, ...]
    source_constraint_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.domain.strip() or not self.subject.strip():
            raise ValueError("Operation requirement domain and subject cannot be empty")
        if not self.allowed_operation_kinds:
            raise ValueError("Operation requirement needs at least one operation kind")
        if not self.source_constraint_ids:
            raise ValueError("Operation requirement needs constraint provenance")
        if self.trigger is OperationTrigger.CONFLICT and not self.source_conflict_ids:
            raise ValueError("Conflict-triggered operations need conflict provenance")
        if self.trigger is not OperationTrigger.CONFLICT and self.source_conflict_ids:
            raise ValueError("Non-conflict operations cannot claim conflict provenance")
        object.__setattr__(
            self,
            "allowed_operation_kinds",
            tuple(sorted(set(self.allowed_operation_kinds), key=lambda item: item.value)),
        )
        object.__setattr__(
            self, "source_conflict_ids", tuple(sorted(set(self.source_conflict_ids)))
        )
        object.__setattr__(
            self, "source_constraint_ids", tuple(sorted(set(self.source_constraint_ids)))
        )

    @property
    def requirement_id(self) -> str:
        digest = hashlib.sha256(_canonical_json(self.to_dict()).encode()).hexdigest()[:16]
        return f"operation-requirement-{digest}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "subject": self.subject,
            "trigger": self.trigger.value,
            "allowed_operation_kinds": [
                item.value for item in self.allowed_operation_kinds
            ],
            "source_conflict_ids": list(self.source_conflict_ids),
            "source_constraint_ids": list(self.source_constraint_ids),
        }


@dataclass(frozen=True)
class OperationPlan:
    requirements: tuple[OperationRequirement, ...] = ()
    unsupported_conflict_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "requirements",
            tuple(sorted(self.requirements, key=lambda item: item.requirement_id)),
        )
        object.__setattr__(
            self,
            "unsupported_conflict_ids",
            tuple(sorted(set(self.unsupported_conflict_ids))),
        )

    @property
    def plan_id(self) -> str:
        digest = hashlib.sha256(_canonical_json(self.semantic_dict()).encode()).hexdigest()[:16]
        return f"operation-plan-{digest}"

    @property
    def source_constraint_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    constraint_id
                    for requirement in self.requirements
                    for constraint_id in requirement.source_constraint_ids
                }
            )
        )

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OPERATION_PLAN_SCHEMA_VERSION,
            "requirements": [item.to_dict() for item in self.requirements],
            "unsupported_conflict_ids": list(self.unsupported_conflict_ids),
        }

    def to_dict(self) -> dict[str, Any]:
        return {"plan_id": self.plan_id, **self.semantic_dict()}


@dataclass(frozen=True)
class OperationGuardDecision:
    accepted: bool
    policy_id: str
    plan: OperationPlan
    reason: str | None = None
    details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise ValueError("Operation guard policy_id cannot be empty")
        if not self.accepted and not (self.reason or "").strip():
            raise ValueError("Rejected operation guard decisions need a reason")
        json.dumps(self.details or {}, ensure_ascii=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "plan": self.plan.to_dict(),
        }
