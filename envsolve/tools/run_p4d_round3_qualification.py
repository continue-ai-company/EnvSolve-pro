#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any
import uuid


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve.context.models import normalize_packages, validate_name
from envsolve.state import audit_state_artifacts
from envsolve.tools.run_p4d_capability_validation import (
    DockerExecutor,
    _docker_json,
    _image_identity,
    _sha256,
    _verify_file,
    _write_json_atomic,
)


def _result(value: Any) -> dict[str, Any]:
    return {
        "exit_code": value.exit_code,
        "stdout": value.stdout,
        "stderr": value.stderr,
        "duration_seconds": value.duration_seconds,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Qualify P4D capability package candidates in clean containers."
    )
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    prereg_path = args.preregistration.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite qualification artifact: {output}")
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    if prereg.get("preregistration_id") != "p4d-capability-round3-v1":
        raise ValueError("Unexpected P4D Round 3 preregistration identifier")
    round2_result_path = _verify_file(
        WORKSPACE_ROOT,
        prereg["round2"]["result"],
        "round2 result",
    )
    _verify_file(WORKSPACE_ROOT, prereg["round2"]["freeze"], "round2 freeze")
    round2 = json.loads(round2_result_path.read_text(encoding="utf-8"))
    artifact = round2["artifact"]
    artifact_root = WORKSPACE_ROOT / artifact["root"]
    event_log = artifact_root / "state.jsonl"
    snapshot = artifact_root / "snapshot.json"
    audit = audit_state_artifacts(event_log, snapshot, artifact["case_id"])
    if (
        not audit.valid
        or audit.snapshot_hash != artifact["snapshot_hash"]
        or _sha256(event_log) != artifact["event_log_sha256"]
        or _sha256(snapshot) != artifact["snapshot_sha256"]
    ):
        raise ValueError("Round 2 source artifact changed or failed audit")
    state = json.loads(snapshot.read_text(encoding="utf-8"))
    details = state["evidence"][
        "evidence-packages-discovery-pg_config-query-details"
    ]["value"]
    capability = validate_name(details["capability"], "capability")
    if capability != prereg["target"]["subject"]:
        raise ValueError("Round 2 candidate subject changed")
    candidates = tuple(
        normalize_packages(
            sorted({item["package"] for item in details["candidates"]})
        )
    )
    if not candidates or len(candidates) > prereg["qualification"]["max_candidates"]:
        raise ValueError("Round 2 candidate count violates Round 3 preregistration")
    image = _image_identity(prereg["image"])
    local_image = _docker_json("image", "inspect", image.reference)[0]
    if local_image.get("Id") != image.image_id or round2["image"] != image.to_dict():
        raise ValueError("Round 3 image identity changed")

    rows: list[dict[str, Any]] = []
    for package in candidates:
        container = f"envsolve-p4d-r3q-{uuid.uuid4().hex[:12]}"
        created = False
        try:
            create = subprocess.run(
                [
                    "docker",
                    "create",
                    "--network",
                    "bridge",
                    "--name",
                    container,
                    image.reference,
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
            record = _docker_json("inspect", container)[0]
            if record.get("Mounts"):
                raise ValueError("Qualification container unexpectedly has mounts")
            start = subprocess.run(
                ["docker", "start", container],
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            if start.returncode != 0:
                raise RuntimeError(start.stderr.strip() or "docker start failed")
            executor = DockerExecutor(container, timeout_seconds=180.0)
            commands = (
                "apt-get update",
                f"apt-get install -y -- {shlex.quote(package)}",
                f"command -v -- {shlex.quote(capability)}",
                f"{shlex.quote(capability)} --version",
            )
            results = []
            for command in commands:
                result = executor.execute(command)
                results.append(_result(result))
                if result.exit_code != 0:
                    break
            qualified = (
                len(results) == 4
                and all(item["exit_code"] == 0 for item in results)
                and bool(results[-1]["stdout"].strip())
            )
            rows.append(
                {
                    "package": package,
                    "commands": list(commands[: len(results)]),
                    "results": results,
                    "qualified": qualified,
                }
            )
        finally:
            if created:
                subprocess.run(
                    ["docker", "rm", "-f", container],
                    text=True,
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
    qualified_packages = sorted(
        row["package"] for row in rows if row["qualified"]
    )
    value = {
        "schema_version": "1.0.0",
        "qualification_id": "p4d-capability-round3-qualification-v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "development_only": True,
        "preregistration": {
            "path": str(prereg_path.relative_to(WORKSPACE_ROOT)),
            "sha256": _sha256(prereg_path),
        },
        "round2_result_sha256": _sha256(round2_result_path),
        "image": image.to_dict(),
        "capability": capability,
        "candidate_order": list(candidates),
        "candidates": rows,
        "qualified_packages": qualified_packages,
        "selected_package": qualified_packages[0] if qualified_packages else None,
        "isolation": {
            "network": "bridge",
            "network_endpoints": ["configured apt sources"],
            "repository_mounted": False,
            "mounts": [],
        },
        "integrity": prereg["integrity"],
    }
    _write_json_atomic(output, value)
    print(
        json.dumps(
            {
                "candidates": [
                    {"package": row["package"], "qualified": row["qualified"]}
                    for row in rows
                ],
                "selected_package": value["selected_package"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if qualified_packages else 1


if __name__ == "__main__":
    raise SystemExit(main())
