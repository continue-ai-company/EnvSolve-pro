from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable


@dataclass(frozen=True)
class HeartbeatAnalysis:
    complete: bool
    sequence_valid: bool
    suspicious_gaps: tuple[float, ...]

    @property
    def suspend_suspected(self) -> bool:
        return bool(self.suspicious_gaps)


def analyze_heartbeat_records(
    records: list[dict[str, Any]],
    suspend_gap_seconds: float,
) -> HeartbeatAnalysis:
    sequence_valid = all(
        record.get("sequence") == index for index, record in enumerate(records)
    )
    complete = bool(
        records
        and records[0].get("event") == "started"
        and records[-1].get("event") == "stopped"
    )
    suspicious = tuple(
        float(record["gap_seconds"])
        for record in records
        if isinstance(record.get("gap_seconds"), (int, float))
        and float(record["gap_seconds"]) > suspend_gap_seconds
    )
    return HeartbeatAnalysis(complete, sequence_valid, suspicious)


class RunHeartbeat:
    def __init__(
        self,
        path: Path,
        interval_seconds: float = 5.0,
        suspend_gap_seconds: float = 30.0,
        *,
        utc_now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        if interval_seconds <= 0 or suspend_gap_seconds <= interval_seconds:
            raise ValueError("Heartbeat gap threshold must exceed its interval")
        self.path = path
        self.interval_seconds = interval_seconds
        self.suspend_gap_seconds = suspend_gap_seconds
        self._utc_now = utc_now or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic or time.monotonic
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._write_lock = threading.Lock()
        self._sequence = 0
        self._previous_utc: datetime | None = None

    def _append(self, event: str) -> None:
        now = self._utc_now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Heartbeat timestamps must include a UTC offset")
        gap = (
            max((now - self._previous_utc).total_seconds(), 0.0)
            if self._previous_utc is not None
            else None
        )
        record = {
            "schema_version": "1.0.0",
            "sequence": self._sequence,
            "event": event,
            "utc": now.astimezone(timezone.utc).isoformat(),
            "monotonic_seconds": self._monotonic(),
            "gap_seconds": gap,
            "pid": os.getpid(),
        }
        with self._write_lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        self._sequence += 1
        self._previous_utc = now

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self._append("heartbeat")

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")
        self._append("started")
        self._thread = threading.Thread(
            target=self._run,
            name="envsolve-run-heartbeat",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_seconds + 1.0)
        self._append("stopped")

    def __enter__(self) -> "RunHeartbeat":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()
