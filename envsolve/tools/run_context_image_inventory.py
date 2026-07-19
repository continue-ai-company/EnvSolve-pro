#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any
import uuid


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve.context import ContextAcquisitionPolicy, build_repair_context
from envsolve.solver import CommandResult, SolverStateSession, StatefulSolverLoop
from envsolve.state import audit_state_artifacts


DEFAULT_IMAGE = "ghcr.io/jetbrains-research/envbench-python:latest"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _docker_json(*args: str) -> Any:
    process = subprocess.run(
        ["docker", *args],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or f"docker {' '.join(args)} failed")
    return json.loads(process.stdout)


class DockerContextExecutor:
    def __init__(self, container: str, timeout_seconds: float = 30.0) -> None:
        self.container = container
        self.timeout_seconds = timeout_seconds
        self.commands: list[str] = []

    def execute(self, command: str) -> CommandResult:
        self.commands.append(command)
        started = time.monotonic()
        try:
            process = subprocess.run(
                ["docker", "exec", self.container, "bash", "-lc", command],
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            return CommandResult(
                exit_code=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
                duration_seconds=time.monotonic() - started,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else exc.stderr
            return CommandResult(
                exit_code=124,
                stdout=stdout or "",
                stderr=stderr or "context probe timed out",
                duration_seconds=time.monotonic() - started,
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run case-free context inventory in an evaluator image."
    )
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    event_log = output_root / "state.jsonl"
    snapshot = output_root / "snapshot.json"
    if event_log.exists() or snapshot.exists():
        raise FileExistsError(f"Refusing to overwrite context artifact: {output_root}")

    image_record = _docker_json("image", "inspect", args.image)[0]
    image_id = str(image_record["Id"])
    case_id = f"case-free-context:{image_id}"
    session = SolverStateSession(
        event_log,
        snapshot,
        {
            "case_id": case_id,
            "repository": "none",
            "revision": image_id,
            "language": "infrastructure",
            "split": "case-free",
            "tags": ["p4b-context", "no-benchmark-repository"],
        },
    )
    session.profile_repository(
        {
            "kind": "case-free-evaluator-image",
            "image_reference": args.image,
            "image_id": image_id,
            "repo_digests": image_record.get("RepoDigests", []),
            "architecture": image_record.get("Architecture"),
            "os": image_record.get("Os"),
            "benchmark_repository_mounted": False,
            "network_enabled": False,
        }
    )

    container = f"envsolve-context-{uuid.uuid4().hex[:12]}"
    created = False
    try:
        create = subprocess.run(
            [
                "docker",
                "create",
                "--network",
                "none",
                "--name",
                container,
                args.image,
                "sleep",
                "infinity",
            ],
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if create.returncode != 0:
            raise RuntimeError(create.stderr.strip() or "docker create failed")
        created = True
        container_record = _docker_json("inspect", container)[0]
        mounts = container_record.get("Mounts", [])
        if mounts:
            raise ValueError(f"Case-free context container has mounts: {mounts}")
        start = subprocess.run(
            ["docker", "start", container],
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if start.returncode != 0:
            raise RuntimeError(start.stderr.strip() or "docker start failed")
        executor = DockerContextExecutor(container)
        result = StatefulSolverLoop(
            session,
            executor,
            max_actions=8,
            goal_id="context-acquisition",
            goal_description="Acquire case-free evaluator context",
        ).run(ContextAcquisitionPolicy(session))
    finally:
        if created:
            subprocess.run(
                ["docker", "rm", "-f", container],
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )

    context_report = build_repair_context(session.reconstruct())
    audit = audit_state_artifacts(event_log, snapshot, case_id)
    if not audit.valid:
        raise ValueError(f"Context inventory state audit failed: {audit.errors}")
    summary = {
        "schema_version": "1.0.0",
        "validation_id": "p4b-case-free-image-context-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "image": {
            "reference": args.image,
            "id": image_id,
            "repo_digests": image_record.get("RepoDigests", []),
            "architecture": image_record.get("Architecture"),
            "os": image_record.get("Os"),
        },
        "isolation": {
            "benchmark_repository_mounted": False,
            "mounts": [],
            "network": "none",
        },
        "result": result.to_dict(),
        "context": context_report.to_dict(),
        "artifact": {
            "root": str(output_root.relative_to(WORKSPACE_ROOT)),
            "case_id": case_id,
            "event_count": audit.event_count,
            "snapshot_hash": audit.snapshot_hash,
            "event_log_sha256": _sha256(event_log),
            "snapshot_sha256": _sha256(snapshot),
            "audit_valid": audit.valid,
        },
        "integrity": {
            "model_requests": 0,
            "new_benchmark_executions": 0,
            "new_benchmark_cases": 0,
            "canary20_inspected": False,
            "official_test100_inspected": False,
        },
    }
    _write_json_atomic(args.summary.resolve(), summary)
    print(
        json.dumps(
            {
                "goal_status": result.goal_status,
                "actions": result.actions_executed,
                "context": context_report.context.to_dict(),
                "audit_valid": audit.valid,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.goal_status == "satisfied" else 1


if __name__ == "__main__":
    raise SystemExit(main())
