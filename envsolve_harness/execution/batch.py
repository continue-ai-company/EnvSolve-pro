from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from typing import Any

from envsolve_harness.core.io import read_json, write_json


def terminate_process_group(process: subprocess.Popen[str], grace_seconds: float = 5.0) -> bool:
    if process.poll() is not None:
        return False
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=grace_seconds)
    return True


class BatchProcessController:
    def __init__(self, termination_grace_seconds: float = 5.0) -> None:
        self.termination_grace_seconds = termination_grace_seconds
        self._cancelled = threading.Event()
        self._lock = threading.Lock()
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._interrupted_cases: set[str] = set()
        self.reason: str | None = None

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def register(self, case_id: str, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._processes[case_id] = process
            cancelled = self._cancelled.is_set()
            if cancelled and process.poll() is None:
                self._interrupted_cases.add(case_id)
        if cancelled:
            terminate_process_group(process, self.termination_grace_seconds)

    def unregister(self, case_id: str) -> None:
        with self._lock:
            self._processes.pop(case_id, None)

    def cancel(self, reason: str) -> tuple[str, ...]:
        self.reason = reason
        self._cancelled.set()
        with self._lock:
            active = list(self._processes.items())
            self._interrupted_cases.update(
                case_id for case_id, process in active if process.poll() is None
            )
        for case_id, process in active:
            terminate_process_group(process, self.termination_grace_seconds)
        with self._lock:
            return tuple(sorted(self._interrupted_cases))

    def was_interrupted(self, case_id: str) -> bool:
        with self._lock:
            return case_id in self._interrupted_cases


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def container_ids_for_case(inspections: list[dict[str, Any]], case_root: Path) -> tuple[str, ...]:
    matches: list[str] = []
    for inspection in inspections:
        mounts = inspection.get("Mounts", [])
        belongs_to_case = any(
            isinstance(mount, dict)
            and isinstance(mount.get("Source"), str)
            and _inside(case_root, Path(mount["Source"]))
            for mount in mounts
        )
        container_id = inspection.get("Id")
        if belongs_to_case and isinstance(container_id, str):
            matches.append(container_id)
    return tuple(sorted(matches))


def cleanup_case_containers(
    case_root: Path,
    attempts: int = 3,
    retry_delay_seconds: float = 0.5,
) -> tuple[str, ...]:
    removed: set[str] = set()
    for attempt in range(attempts):
        listed = subprocess.run(
            ["docker", "ps", "-aq", "--no-trunc"],
            capture_output=True,
            text=True,
            check=False,
        )
        if listed.returncode != 0:
            break
        container_ids = listed.stdout.split()
        if container_ids:
            inspected = subprocess.run(
                ["docker", "inspect", *container_ids],
                capture_output=True,
                text=True,
                check=False,
            )
            if inspected.returncode == 0:
                try:
                    records = json.loads(inspected.stdout)
                except json.JSONDecodeError:
                    records = []
                if isinstance(records, list):
                    matches = container_ids_for_case(records, case_root)
                    for container_id in matches:
                        subprocess.run(
                            ["docker", "rm", "-f", container_id],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        removed.add(container_id)
        if attempt + 1 < attempts:
            time.sleep(retry_delay_seconds)
    return tuple(sorted(removed))


def mark_case_interrupted(
    case_root: Path,
    reason: str,
    process_exit_code: int | None,
    cleaned_container_ids: tuple[str, ...],
) -> bool:
    manifest_path = case_root / "manifest.json"
    status_path = case_root / "status.json"
    if not manifest_path.is_file() or not status_path.is_file():
        return False
    manifest = read_json(manifest_path)
    if manifest.get("result") is not None:
        return False
    previous = read_json(status_path)
    write_json(
        status_path,
        {
            "state": "interrupted",
            "previous_state": previous.get("state"),
            "reason": reason,
            "process_exit_code": process_exit_code,
            "cleaned_container_ids": list(cleaned_container_ids),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return True
