from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


@dataclass(frozen=True)
class InitialConstraintEvidence:
    """A provenance-bearing observation admitted before the first action."""

    evidence_id: str
    kind: str
    source: str
    value: dict[str, Any]
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not all(
            isinstance(item, str) and item.strip()
            for item in (self.evidence_id, self.kind, self.source)
        ):
            raise ValueError("Initial constraint evidence identifiers cannot be empty")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not 0 <= self.confidence <= 1
        ):
            raise ValueError("Initial constraint evidence confidence must be in [0, 1]")
        try:
            json.dumps(self.value, ensure_ascii=True)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Initial constraint evidence must be JSON serializable"
            ) from exc
