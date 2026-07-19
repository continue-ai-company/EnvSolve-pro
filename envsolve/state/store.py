from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
from typing import Any

from envsolve.state.events import EventType, GENESIS_HASH, StateEvent
from envsolve.state.reducer import EnvironmentState, apply_event, reduce_events


class EventStore:
    def __init__(self, path: Path, case_id: str) -> None:
        self.path = path
        self.case_id = case_id
        self._cached_events: tuple[StateEvent, ...] | None = None
        self._cached_state: EnvironmentState | None = None
        self._cached_signature: tuple[int, int, int, int] | None = None

    @staticmethod
    def _signature(handle: Any) -> tuple[int, int, int, int]:
        value = os.fstat(handle.fileno())
        return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)

    def _load_handle(
        self,
        handle: Any,
    ) -> tuple[tuple[StateEvent, ...], EnvironmentState]:
        signature = self._signature(handle)
        if (
            self._cached_signature == signature
            and self._cached_events is not None
            and self._cached_state is not None
        ):
            return self._cached_events, deepcopy(self._cached_state)
        events = tuple(self._read_handle(handle))
        state = reduce_events(self.case_id, events)
        self._cached_events = events
        self._cached_state = deepcopy(state)
        self._cached_signature = signature
        return events, state

    @staticmethod
    def _read_handle(handle: Any) -> list[StateEvent]:
        handle.seek(0)
        events: list[StateEvent] = []
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                events.append(StateEvent.from_dict(value))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid state log at line {line_number}: {exc}") from exc
        return events

    def read(self) -> list[StateEvent]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            try:
                events, _ = self._load_handle(handle)
                return list(deepcopy(events))
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def append(self, event_type: EventType | str, payload: dict[str, Any]) -> StateEvent:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                events, state = self._load_handle(handle)
                event = StateEvent.create(
                    case_id=self.case_id,
                    sequence=state.last_sequence + 1,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    event_type=event_type,
                    payload=payload,
                    previous_hash=state.last_event_hash,
                )
                apply_event(state, event)
                handle.seek(0, os.SEEK_END)
                handle.write(json.dumps(event.to_dict(), ensure_ascii=True, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                self._cached_events = (*events, event)
                self._cached_state = deepcopy(state)
                self._cached_signature = self._signature(handle)
                return event
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def reconstruct(self) -> EnvironmentState:
        if not self.path.exists():
            return EnvironmentState(case_id=self.case_id)
        with self.path.open(encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            try:
                _, state = self._load_handle(handle)
                return state
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
