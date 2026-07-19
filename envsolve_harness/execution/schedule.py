from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
import time
from typing import Any

from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.execution.batch import terminate_process_group


TERMINAL_STATES = {
    "process_finished",
    "process_error",
    "timed_out",
    "interrupted",
    "orphaned",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ScheduleProgress:
    def __init__(
        self,
        path: Path,
        schedule_path: Path,
        schedule_sha256: str,
        execution: dict[str, Any] | None = None,
    ) -> None:
        self.path = path
        self.schedule_path = str(schedule_path.resolve())
        self.schedule_sha256 = schedule_sha256
        self.execution = execution or {}
        self._outcomes: dict[int, dict[str, Any]] = {}
        if path.is_file():
            persisted = read_json(path)
            if persisted.get("schema_version") != "2.0.0":
                raise ValueError(f"Unsupported progress schema in {path}")
            if (
                persisted.get("schedule") != self.schedule_path
                or persisted.get("schedule_sha256") != schedule_sha256
            ):
                raise ValueError("Progress belongs to a different frozen schedule")
            if persisted.get("execution", {}) != self.execution:
                raise ValueError("Progress uses different frozen execution settings")
            for outcome in persisted.get("outcomes", []):
                position = int(outcome["position"])
                if position in self._outcomes:
                    raise ValueError(f"Duplicate progress position: {position}")
                self._outcomes[position] = dict(outcome)

    @property
    def outcomes(self) -> list[dict[str, Any]]:
        return [self._outcomes[position] for position in sorted(self._outcomes)]

    def _write(self) -> None:
        write_json(
            self.path,
            {
                "schema_version": "2.0.0",
                "schedule": self.schedule_path,
                "schedule_sha256": self.schedule_sha256,
                "execution": self.execution,
                "updated_at": _now(),
                "outcomes": self.outcomes,
            },
        )

    def recover_orphans(self) -> tuple[int, ...]:
        recovered: list[int] = []
        for position, outcome in self._outcomes.items():
            if outcome.get("state") == "running":
                outcome.update(
                    {
                        "state": "orphaned",
                        "finished_at": _now(),
                        "reason": "coordinator stopped before recording a terminal state",
                    }
                )
                recovered.append(position)
        if recovered:
            self._write()
        return tuple(sorted(recovered))

    def contains(self, position: int) -> bool:
        return position in self._outcomes

    def begin(self, identity: dict[str, Any]) -> None:
        position = int(identity["position"])
        if position in self._outcomes:
            raise ValueError(f"Schedule position {position} already has a recorded outcome")
        self._outcomes[position] = {
            **identity,
            "state": "running",
            "started_at": _now(),
        }
        self._write()

    def complete(self, position: int, outcome: dict[str, Any]) -> None:
        current = self._outcomes.get(position)
        if current is None or current.get("state") != "running":
            raise ValueError(f"Schedule position {position} is not running")
        if outcome.get("state") not in TERMINAL_STATES:
            raise ValueError(f"Invalid terminal schedule state: {outcome.get('state')!r}")
        for key in ("position", "case_id", "run_id", "method"):
            if key in outcome and outcome[key] != current.get(key):
                raise ValueError(f"Outcome changes frozen identity field {key!r}")
        current.update(outcome)
        current["finished_at"] = _now()
        self._write()


def run_scheduled_process(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: float,
    termination_grace_seconds: float = 5.0,
) -> dict[str, Any]:
    if timeout_seconds <= 0:
        raise ValueError("Episode timeout must be positive")
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except OSError as exc:
        return {
            "state": "process_error",
            "process_exit_code": None,
            "duration_seconds": time.monotonic() - started,
            "stdout_tail": "",
            "stderr_tail": f"{type(exc).__name__}: {exc}",
            "reason": "unable to start episode process",
        }
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        state = "process_finished"
        reason = None
    except subprocess.TimeoutExpired:
        terminate_process_group(process, termination_grace_seconds)
        stdout, stderr = process.communicate()
        state = "timed_out"
        reason = f"episode exceeded hard timeout of {timeout_seconds:g}s"
    except KeyboardInterrupt:
        terminate_process_group(process, termination_grace_seconds)
        stdout, stderr = process.communicate()
        state = "interrupted"
        reason = "coordinator interrupted"
    return {
        "state": state,
        "process_exit_code": process.returncode,
        "duration_seconds": time.monotonic() - started,
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-4000:],
        "reason": reason,
    }
