from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import json
import re
from typing import Any


EVENT_SCHEMA_VERSION = "1.0.0"
GENESIS_HASH = "0" * 64


class EventType(str, Enum):
    RUN_STARTED = "run_started"
    REPOSITORY_PROFILED = "repository_profiled"
    EVIDENCE_RECORDED = "evidence_recorded"
    CONSTRAINT_UPSERTED = "constraint_upserted"
    HYPOTHESIS_UPSERTED = "hypothesis_upserted"
    GOAL_UPSERTED = "goal_upserted"
    ENVIRONMENT_UPDATED = "environment_updated"
    ACTION_PROPOSED = "action_proposed"
    ACTION_STARTED = "action_started"
    ACTION_FINISHED = "action_finished"
    FAILURE_RECORDED = "failure_recorded"
    VERIFICATION_RECORDED = "verification_recorded"
    ROLLBACK_RECORDED = "rollback_recorded"


REQUIRED_PAYLOAD_FIELDS: dict[EventType, frozenset[str]] = {
    EventType.RUN_STARTED: frozenset({"case"}),
    EventType.REPOSITORY_PROFILED: frozenset({"profile"}),
    EventType.EVIDENCE_RECORDED: frozenset(
        {"evidence_id", "kind", "source", "value", "confidence"}
    ),
    EventType.CONSTRAINT_UPSERTED: frozenset(
        {"constraint_id", "kind", "expression", "status", "evidence_ids"}
    ),
    EventType.HYPOTHESIS_UPSERTED: frozenset(
        {"hypothesis_id", "statement", "confidence", "evidence_ids", "status"}
    ),
    EventType.GOAL_UPSERTED: frozenset({"goal_id", "description", "status"}),
    EventType.ENVIRONMENT_UPDATED: frozenset({"name", "value", "source"}),
    EventType.ACTION_PROPOSED: frozenset(
        {"action_id", "action_type", "command", "rationale", "preconditions"}
    ),
    EventType.ACTION_STARTED: frozenset({"action_id"}),
    EventType.ACTION_FINISHED: frozenset({"action_id", "exit_code", "observation"}),
    EventType.FAILURE_RECORDED: frozenset({"failure_id", "category", "message"}),
    EventType.VERIFICATION_RECORDED: frozenset(
        {"verification_id", "level", "verifier", "passed", "details"}
    ),
    EventType.ROLLBACK_RECORDED: frozenset({"action_id", "reason"}),
}


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def compute_event_hash(value: dict[str, Any]) -> str:
    unsigned = {key: item for key, item in value.items() if key != "event_hash"}
    return hashlib.sha256(_canonical_json(unsigned).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StateEvent:
    schema_version: str
    case_id: str
    sequence: int
    timestamp: str
    event_type: str
    payload: dict[str, Any]
    previous_hash: str
    event_hash: str

    @classmethod
    def create(
        cls,
        case_id: str,
        sequence: int,
        timestamp: str,
        event_type: EventType | str,
        payload: dict[str, Any],
        previous_hash: str,
    ) -> "StateEvent":
        normalized_type = EventType(event_type)
        value = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "case_id": case_id,
            "sequence": sequence,
            "timestamp": timestamp,
            "event_type": normalized_type.value,
            "payload": payload,
            "previous_hash": previous_hash,
        }
        event = cls(**value, event_hash=compute_event_hash(value))
        event.validate()
        return event

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "StateEvent":
        try:
            sequence = value["sequence"]
            payload = value["payload"]
            if isinstance(sequence, bool) or not isinstance(sequence, int):
                raise TypeError("sequence must be an integer")
            if not isinstance(payload, dict):
                raise TypeError("payload must be an object")
            event = cls(
                schema_version=str(value["schema_version"]),
                case_id=str(value["case_id"]),
                sequence=sequence,
                timestamp=str(value["timestamp"]),
                event_type=str(value["event_type"]),
                payload=dict(payload),
                previous_hash=str(value["previous_hash"]),
                event_hash=str(value["event_hash"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid state event: {exc}") from exc
        event.validate()
        return event

    def validate(self) -> None:
        if self.schema_version != EVENT_SCHEMA_VERSION:
            raise ValueError(f"Unsupported event schema: {self.schema_version!r}")
        if not self.case_id:
            raise ValueError("State event case_id cannot be empty")
        if self.sequence < 0:
            raise ValueError("State event sequence cannot be negative")
        try:
            timestamp = datetime.fromisoformat(self.timestamp)
        except ValueError as exc:
            raise ValueError(f"Invalid state event timestamp: {self.timestamp!r}") from exc
        if timestamp.utcoffset() != timedelta(0):
            raise ValueError("State event timestamp must include the UTC offset")
        event_type = EventType(self.event_type)
        missing = REQUIRED_PAYLOAD_FIELDS[event_type] - self.payload.keys()
        if missing:
            raise ValueError(f"{event_type.value} payload is missing fields: {sorted(missing)}")
        try:
            _canonical_json(self.payload)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"State event payload is not JSON serializable: {exc}") from exc
        if not re.fullmatch(r"[0-9a-f]{64}", self.previous_hash) or not re.fullmatch(
            r"[0-9a-f]{64}", self.event_hash
        ):
            raise ValueError("State event hashes must be 64 hexadecimal characters")
        if compute_event_hash(self.to_dict()) != self.event_hash:
            raise ValueError(f"State event hash mismatch at sequence {self.sequence}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
