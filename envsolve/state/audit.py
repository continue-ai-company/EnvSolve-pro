from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

from envsolve.state.store import EventStore


@dataclass
class StateAuditReport:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)
    event_count: int = 0
    snapshot_hash: str | None = None

    def error(self, message: str) -> None:
        self.valid = False
        self.errors.append(message)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def audit_state_artifacts(
    event_log: Path,
    snapshot_path: Path,
    case_id: str,
    require_terminal_actions: bool = True,
) -> StateAuditReport:
    report = StateAuditReport()
    report.checks["event_log_exists"] = event_log.is_file()
    report.checks["snapshot_exists"] = snapshot_path.is_file()
    if not event_log.is_file():
        report.error("State event log is missing")
    if not snapshot_path.is_file():
        report.error("State snapshot is missing")
    if not report.valid:
        return report

    try:
        store = EventStore(event_log, case_id)
        events = store.read()
        reconstructed = store.reconstruct().to_dict()
    except (OSError, TypeError, ValueError) as exc:
        report.error(f"State reconstruction failed: {type(exc).__name__}: {exc}")
        return report

    report.event_count = len(events)
    report.snapshot_hash = reconstructed["snapshot_hash"]
    report.checks["has_run_started"] = bool(events)
    if not events:
        report.error("State trajectory is empty")

    try:
        persisted = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        report.error(f"State snapshot cannot be parsed: {type(exc).__name__}: {exc}")
        return report
    report.checks["snapshot_matches_reconstruction"] = persisted == reconstructed
    if persisted != reconstructed:
        report.error("Persisted state snapshot does not match event reconstruction")

    actions = reconstructed.get("actions", {})
    terminal = isinstance(actions, dict) and all(
        isinstance(action, dict)
        and action.get("status") in {"succeeded", "failed", "rolled_back"}
        for action in actions.values()
    )
    report.checks["actions_terminal"] = terminal
    if require_terminal_actions and not terminal:
        report.error("State trajectory contains a non-terminal action")
    return report
