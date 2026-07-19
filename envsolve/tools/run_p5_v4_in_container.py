#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.verification.native_project import (
    NativeOutcome,
    NativeProjectPlanner,
    evaluate_native_outcome,
)
from envsolve.verification.network_isolation import default_route_present


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bounded_tail(value: bytes, limit: int = 4000) -> str:
    return value[-limit:].decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute P5 V4 project-native evidence.")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--network-marker", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.network_marker.is_file():
        raise RuntimeError("host network-disconnect marker is missing")
    if default_route_present():
        raise RuntimeError("container still has a default network route")

    project_root = args.project_root.resolve()
    with tempfile.TemporaryDirectory(prefix="envsolve-v4-wheel-") as directory:
        wheel_directory = Path(directory)
        plan = NativeProjectPlanner().plan(
            project_root,
            sys.executable,
            wheel_directory,
        )
        outcome = None
        outcome_artifact = None
        if plan.probe is not None:
            environment = {
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                "PIP_NO_INDEX": "1",
            }
            started = time.monotonic()
            try:
                process = subprocess.run(
                    plan.probe.argv,
                    cwd=project_root,
                    env=environment,
                    capture_output=True,
                    check=False,
                    timeout=300,
                )
                exit_code = process.returncode
                stdout = process.stdout
                stderr = process.stderr
                timed_out = False
            except subprocess.TimeoutExpired as exc:
                exit_code = None
                stdout = exc.stdout if isinstance(exc.stdout, bytes) else (exc.stdout or "").encode()
                stderr = exc.stderr if isinstance(exc.stderr, bytes) else (exc.stderr or "").encode()
                timed_out = True
            wheels = tuple(sorted(path.name for path in wheel_directory.glob("*.whl")))
            outcome = NativeOutcome(exit_code, timed_out, wheels)
            outcome_artifact = {
                "exit_code": exit_code,
                "timed_out": timed_out,
                "duration_seconds": time.monotonic() - started,
                "stdout_sha256": sha_bytes(stdout),
                "stderr_sha256": sha_bytes(stderr),
                "stdout_tail": bounded_tail(stdout),
                "stderr_tail": bounded_tail(stderr),
                "output_artifacts": [
                    {
                        "name": path.name,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                    for path in sorted(wheel_directory.glob("*.whl"))
                ],
            }
        decision = evaluate_native_outcome(plan, outcome)

    probe = plan.probe
    result: dict[str, Any] = {
        "schema": "envsolve-p5-v4-container-v1",
        "python": {"executable": sys.executable, "prefix": sys.prefix},
        "network": {"host_disconnect_marker": True, "default_route_present": False},
        "project_root": str(project_root),
        "plan": {
            "reason": plan.reason,
            "probe": None
            if probe is None
            else {
                "probe_id": probe.probe_id,
                "kind": probe.kind.value,
                "argv": list(probe.argv),
                "config_evidence": [item.__dict__ for item in probe.config_evidence],
            },
        },
        "outcome": outcome_artifact,
        "decision": decision.__dict__,
    }
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
