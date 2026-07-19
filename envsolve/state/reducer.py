from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any, Iterable

from envsolve.state.events import EventType, GENESIS_HASH, StateEvent


@dataclass
class EnvironmentState:
    case_id: str
    last_sequence: int = -1
    last_event_hash: str = GENESIS_HASH
    case: dict[str, Any] | None = None
    repository_profile: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, dict[str, Any]] = field(default_factory=dict)
    constraints: dict[str, dict[str, Any]] = field(default_factory=dict)
    hypotheses: dict[str, dict[str, Any]] = field(default_factory=dict)
    goals: dict[str, dict[str, Any]] = field(default_factory=dict)
    environment: dict[str, dict[str, Any]] = field(default_factory=dict)
    actions: dict[str, dict[str, Any]] = field(default_factory=dict)
    failures: dict[str, dict[str, Any]] = field(default_factory=dict)
    verifications: list[dict[str, Any]] = field(default_factory=list)
    rollbacks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        canonical = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        value["snapshot_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return value


def _record_unique(target: dict[str, dict[str, Any]], key: str, payload: dict[str, Any]) -> None:
    if key in target:
        raise ValueError(f"Duplicate immutable state identifier: {key}")
    target[key] = dict(payload)


def _event_metadata(event: StateEvent, revision: int) -> dict[str, Any]:
    return {
        "event_sequence": event.sequence,
        "event_hash": event.event_hash,
        "recorded_at": event.timestamp,
        "revision": revision,
    }


def _annotate(payload: dict[str, Any], event: StateEvent, revision: int = 1) -> dict[str, Any]:
    return {**payload, "state_metadata": _event_metadata(event, revision)}


def _mark_transition(target: dict[str, Any], event: StateEvent) -> None:
    previous = target.get("state_metadata", {})
    target["state_metadata"] = _event_metadata(event, int(previous.get("revision", 0)) + 1)


def _upsert(
    target: dict[str, dict[str, Any]],
    key: str,
    payload: dict[str, Any],
    event: StateEvent,
) -> None:
    previous = target.get(key, {}).get("state_metadata", {})
    revision = int(previous.get("revision", 0)) + 1
    target[key] = _annotate(payload, event, revision)


def _confidence(payload: dict[str, Any]) -> None:
    value = payload["confidence"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError(f"Confidence must be in [0, 1], got {value!r}")


def _require_references(
    references: Any,
    known: dict[str, dict[str, Any]],
    reference_type: str,
) -> None:
    if not isinstance(references, list) or not all(isinstance(item, str) for item in references):
        raise ValueError(f"{reference_type} references must be a list of strings")
    missing = set(references) - known.keys()
    if missing:
        raise ValueError(f"Unknown {reference_type} references: {sorted(missing)}")


def apply_event(state: EnvironmentState, event: StateEvent) -> None:
    expected_sequence = state.last_sequence + 1
    if event.case_id != state.case_id:
        raise ValueError(f"Event case {event.case_id!r} does not match state case {state.case_id!r}")
    if event.sequence != expected_sequence:
        raise ValueError(f"Expected event sequence {expected_sequence}, got {event.sequence}")
    if event.previous_hash != state.last_event_hash:
        raise ValueError(f"Broken event hash chain at sequence {event.sequence}")

    kind = EventType(event.event_type)
    payload = event.payload
    if kind == EventType.RUN_STARTED:
        if state.case is not None:
            raise ValueError("run_started can only occur once")
        if not isinstance(payload["case"], dict) or payload["case"].get("case_id") != state.case_id:
            raise ValueError("run_started case payload does not match the event case_id")
        state.case = dict(payload["case"])
    elif state.case is None:
        raise ValueError("run_started must be the first state event")
    elif kind == EventType.REPOSITORY_PROFILED:
        previous = state.repository_profile.get("state_metadata", {})
        state.repository_profile = _annotate(
            dict(payload["profile"]),
            event,
            int(previous.get("revision", 0)) + 1,
        )
    elif kind == EventType.EVIDENCE_RECORDED:
        _confidence(payload)
        _record_unique(
            state.evidence,
            str(payload["evidence_id"]),
            _annotate(payload, event),
        )
    elif kind == EventType.CONSTRAINT_UPSERTED:
        if payload["status"] not in {"active", "satisfied", "violated", "superseded"}:
            raise ValueError(f"Invalid constraint status: {payload['status']!r}")
        _require_references(payload["evidence_ids"], state.evidence, "evidence")
        _upsert(state.constraints, str(payload["constraint_id"]), payload, event)
    elif kind == EventType.HYPOTHESIS_UPSERTED:
        _confidence(payload)
        if payload["status"] not in {"active", "confirmed", "rejected"}:
            raise ValueError(f"Invalid hypothesis status: {payload['status']!r}")
        _require_references(payload["evidence_ids"], state.evidence, "evidence")
        _upsert(state.hypotheses, str(payload["hypothesis_id"]), payload, event)
    elif kind == EventType.GOAL_UPSERTED:
        if payload["status"] not in {"pending", "in_progress", "satisfied", "blocked"}:
            raise ValueError(f"Invalid goal status: {payload['status']!r}")
        _upsert(state.goals, str(payload["goal_id"]), payload, event)
    elif kind == EventType.ENVIRONMENT_UPDATED:
        _upsert(state.environment, str(payload["name"]), payload, event)
    elif kind == EventType.ACTION_PROPOSED:
        action_id = str(payload["action_id"])
        _require_references(payload["preconditions"], state.constraints, "constraint")
        _record_unique(
            state.actions,
            action_id,
            _annotate({**payload, "status": "proposed"}, event),
        )
    elif kind == EventType.ACTION_STARTED:
        action_id = str(payload["action_id"])
        action = state.actions.get(action_id)
        if action is None or action["status"] != "proposed":
            raise ValueError(f"Action {action_id!r} cannot start from its current state")
        action.update({"status": "running", "started_at": event.timestamp})
        _mark_transition(action, event)
    elif kind == EventType.ACTION_FINISHED:
        action_id = str(payload["action_id"])
        action = state.actions.get(action_id)
        if action is None or action["status"] != "running":
            raise ValueError(f"Action {action_id!r} cannot finish from its current state")
        exit_code = payload["exit_code"]
        if isinstance(exit_code, bool) or not isinstance(exit_code, int):
            raise ValueError(f"Action exit_code must be an integer, got {exit_code!r}")
        action.update(
            {
                **payload,
                "status": "succeeded" if exit_code == 0 else "failed",
                "finished_at": event.timestamp,
            }
        )
        _mark_transition(action, event)
    elif kind == EventType.FAILURE_RECORDED:
        action_id = payload.get("action_id")
        if action_id is not None and action_id not in state.actions:
            raise ValueError(f"Failure references unknown action: {action_id!r}")
        _record_unique(
            state.failures,
            str(payload["failure_id"]),
            _annotate(payload, event),
        )
    elif kind == EventType.VERIFICATION_RECORDED:
        if not isinstance(payload["level"], str) or not payload["level"].strip():
            raise ValueError("Verification check profile cannot be empty")
        if payload["passed"] is not None and not isinstance(payload["passed"], bool):
            raise ValueError("Verification passed must be boolean or null")
        state.verifications.append(_annotate(payload, event))
    elif kind == EventType.ROLLBACK_RECORDED:
        action_id = str(payload["action_id"])
        action = state.actions.get(action_id)
        if action is None or action["status"] not in {"succeeded", "failed"}:
            raise ValueError(f"Action {action_id!r} cannot be rolled back from its current state")
        action["status"] = "rolled_back"
        _mark_transition(action, event)
        state.rollbacks.append(_annotate(payload, event))

    state.last_sequence = event.sequence
    state.last_event_hash = event.event_hash


def reduce_events(case_id: str, events: Iterable[StateEvent]) -> EnvironmentState:
    state = EnvironmentState(case_id=case_id)
    for event in events:
        apply_event(state, event)
    return state
