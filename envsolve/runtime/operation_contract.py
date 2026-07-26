from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any


OPERATION_RELEVANCE_CONTRACT_SCHEMA = (
    "envsolve-operation-relevance-contract-v1"
)
OPERATION_RELEVANCE_CONTEXT_SCHEMA = (
    "envsolve-operation-relevance-context-v1"
)
_CONTRACT_FIELDS = {
    "schema",
    "target_finding_ids",
    "precondition_evidence_ids",
    "expected_resolved_finding_ids",
    "operation_family",
}
_FAMILY_FIELDS = {"tool", "mechanism", "target"}
_MAX_REFERENCES = 64
_MAX_REFERENCE_CHARS = 256
_MAX_FAMILY_CHARS = 160


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _reference_tuple(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"Operation contract {name} must be a string array")
    if len(value) > _MAX_REFERENCES:
        raise ValueError(
            f"Operation contract {name} exceeds {_MAX_REFERENCES} references"
        )
    normalized: list[str] = []
    for item in value:
        if (
            not isinstance(item, str)
            or not item.strip()
            or len(item) > _MAX_REFERENCE_CHARS
            or "\0" in item
        ):
            raise ValueError(
                f"Operation contract {name} contains an invalid reference"
            )
        normalized.append(item.strip())
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"Operation contract {name} contains duplicate references")
    return tuple(sorted(normalized))


def _family_value(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > _MAX_FAMILY_CHARS
        or "\0" in value
    ):
        raise ValueError(
            f"Operation family {name} must be a bounded non-empty string"
        )
    return " ".join(value.split())


@dataclass(frozen=True)
class OperationFamily:
    """Open, model-declared identity for the newly introduced repair."""

    tool: str
    mechanism: str
    target: str

    @classmethod
    def from_dict(cls, value: Any) -> OperationFamily:
        if not isinstance(value, dict) or set(value) != _FAMILY_FIELDS:
            raise ValueError(
                "Operation family must contain only tool, mechanism, and target"
            )
        return cls(
            tool=_family_value(value["tool"], "tool"),
            mechanism=_family_value(value["mechanism"], "mechanism"),
            target=_family_value(value["target"], "target"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "tool": self.tool,
            "mechanism": self.mechanism,
            "target": self.target,
        }

    @property
    def family_id(self) -> str:
        normalized = {
            key: " ".join(value.casefold().split())
            for key, value in self.to_dict().items()
        }
        digest = hashlib.sha256(
            _canonical_json(normalized).encode("utf-8")
        ).hexdigest()[:20]
        return f"operation-family-{digest}"


@dataclass(frozen=True)
class OperationRelevanceContract:
    target_finding_ids: tuple[str, ...]
    precondition_evidence_ids: tuple[str, ...]
    expected_resolved_finding_ids: tuple[str, ...]
    operation_family: OperationFamily

    def __post_init__(self) -> None:
        if not self.target_finding_ids:
            raise ValueError("Operation contract needs at least one target finding")
        if not self.precondition_evidence_ids:
            raise ValueError(
                "Operation contract needs at least one precondition evidence reference"
            )
        if not self.expected_resolved_finding_ids:
            raise ValueError(
                "Operation contract needs at least one expected resolved finding"
            )
        outside = set(self.expected_resolved_finding_ids) - set(
            self.target_finding_ids
        )
        if outside:
            raise ValueError(
                "Expected resolved findings must be a subset of target findings"
            )

    @classmethod
    def from_dict(cls, value: Any) -> OperationRelevanceContract:
        if not isinstance(value, dict) or set(value) != _CONTRACT_FIELDS:
            raise ValueError(
                "Operation contract has missing or unknown fields"
            )
        if value.get("schema") != OPERATION_RELEVANCE_CONTRACT_SCHEMA:
            raise ValueError("Operation contract schema is unsupported")
        return cls(
            target_finding_ids=_reference_tuple(
                value["target_finding_ids"],
                "target_finding_ids",
            ),
            precondition_evidence_ids=_reference_tuple(
                value["precondition_evidence_ids"],
                "precondition_evidence_ids",
            ),
            expected_resolved_finding_ids=_reference_tuple(
                value["expected_resolved_finding_ids"],
                "expected_resolved_finding_ids",
            ),
            operation_family=OperationFamily.from_dict(
                value["operation_family"]
            ),
        )

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema": OPERATION_RELEVANCE_CONTRACT_SCHEMA,
            "target_finding_ids": list(self.target_finding_ids),
            "precondition_evidence_ids": list(
                self.precondition_evidence_ids
            ),
            "expected_resolved_finding_ids": list(
                self.expected_resolved_finding_ids
            ),
            "operation_family": self.operation_family.to_dict(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.semantic_dict(),
            "contract_id": self.contract_id,
            "operation_family_id": self.operation_family.family_id,
        }

    @property
    def contract_id(self) -> str:
        digest = hashlib.sha256(
            _canonical_json(self.semantic_dict()).encode("utf-8")
        ).hexdigest()[:20]
        return f"operation-contract-{digest}"
