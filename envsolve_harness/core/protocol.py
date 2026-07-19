from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class SuccessCriteria:
    metric: str
    operator: str
    value: Any

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SuccessCriteria":
        required = {"metric", "operator", "value"}
        missing = required - value.keys()
        if missing:
            raise ValueError(f"Success criterion is missing fields: {sorted(missing)}")
        operator = str(value["operator"])
        if operator not in {"eq", "ne", "lt", "lte", "gt", "gte"}:
            raise ValueError(f"Unsupported success operator: {operator!r}")
        return cls(str(value["metric"]), operator, value["value"])

    def evaluate(self, metrics: Mapping[str, Any]) -> bool:
        if self.metric not in metrics:
            return False
        observed = metrics[self.metric]
        operations = {
            "eq": lambda: observed == self.value,
            "ne": lambda: observed != self.value,
            "lt": lambda: observed < self.value,
            "lte": lambda: observed <= self.value,
            "gt": lambda: observed > self.value,
            "gte": lambda: observed >= self.value,
        }
        try:
            return bool(operations[self.operator]())
        except TypeError:
            return False


@dataclass(frozen=True)
class ExperimentProtocol:
    protocol_id: str
    schema_version: str
    benchmark: str
    language: str
    success: tuple[SuccessCriteria, ...]
    integrity_rules: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ExperimentProtocol":
        required = {"protocol_id", "schema_version", "benchmark", "language", "success"}
        missing = required - value.keys()
        if missing:
            raise ValueError(f"Protocol is missing required fields: {sorted(missing)}")
        return cls(
            protocol_id=str(value["protocol_id"]),
            schema_version=str(value["schema_version"]),
            benchmark=str(value["benchmark"]),
            language=str(value["language"]),
            success=tuple(SuccessCriteria.from_dict(item) for item in value["success"]["all_of"]),
            integrity_rules=tuple(str(rule) for rule in value.get("integrity_rules", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_id": self.protocol_id,
            "schema_version": self.schema_version,
            "benchmark": self.benchmark,
            "language": self.language,
            "success": {
                "all_of": [asdict(criterion) for criterion in self.success],
            },
            "integrity_rules": list(self.integrity_rules),
        }

    def is_official_pass(self, metrics: Mapping[str, Any]) -> bool:
        return all(criterion.evaluate(metrics) for criterion in self.success)


def load_protocol(path: Path) -> ExperimentProtocol:
    with path.open(encoding="utf-8") as handle:
        return ExperimentProtocol.from_dict(json.load(handle))
