#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import subprocess
import sys
import uuid


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve.context.models import normalize_packages, validate_name
from envsolve.tools.run_p4d_capability_validation import (
    DockerExecutor,
    _docker_json,
    _image_identity,
    _sha256,
    _write_json_atomic,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Retry infrastructure-blocked P4D candidates.")
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    prereg_path = args.preregistration.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite retry artifact: {output}")
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    if prereg.get("preregistration_id") != "p4d-capability-round3-retry1-v1":
        raise ValueError("Unexpected retry preregistration identifier")
    parent_path = WORKSPACE_ROOT / prereg["parent"]["path"]
    if _sha256(parent_path) != prereg["parent"]["sha256"]:
        raise ValueError("Parent qualification artifact changed")
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    image = _image_identity(parent["image"])
    if _docker_json("image", "inspect", image.reference)[0].get("Id") != image.image_id:
        raise ValueError("Local evaluator image identity changed")
    capability = validate_name(parent["capability"], "capability")
    eligible = []
    for row in parent["candidates"]:
        results = row["results"]
        if (
            len(results) == 1
            and results[0]["exit_code"] == 124
            and row["commands"] == ["apt-get update"]
        ):
            eligible.append(normalize_packages([row["package"]])[0])
    if not eligible:
        raise ValueError("No infrastructure-blocked candidate is eligible for retry")
    rows = []
    for package in sorted(eligible):
        container = f"envsolve-p4d-r3retry-{uuid.uuid4().hex[:10]}"
        created = False
        try:
            create = subprocess.run(
                ["docker", "create", "--network", "bridge", "--name", container, image.reference, "sleep", "infinity"],
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
            )
            if create.returncode != 0:
                raise RuntimeError(create.stderr.strip() or "docker create failed")
            created = True
            if _docker_json("inspect", container)[0].get("Mounts"):
                raise ValueError("Retry container unexpectedly has mounts")
            start = subprocess.run(
                ["docker", "start", container],
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            if start.returncode != 0:
                raise RuntimeError(start.stderr.strip() or "docker start failed")
            executor = DockerExecutor(
                container,
                timeout_seconds=float(prereg["policy"]["timeout_seconds"]),
            )
            commands = (
                "apt-get update",
                f"apt-get install -y -- {shlex.quote(package)}",
                f"command -v -- {shlex.quote(capability)}",
                f"{shlex.quote(capability)} --version",
            )
            results = []
            for command in commands:
                result = executor.execute(command)
                results.append(
                    {
                        "exit_code": result.exit_code,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "duration_seconds": result.duration_seconds,
                    }
                )
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
    qualified = sorted(row["package"] for row in rows if row["qualified"])
    value = {
        "schema_version": "1.0.0",
        "retry_id": "p4d-capability-round3-retry1-v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "development_only": True,
        "preregistration_sha256": _sha256(prereg_path),
        "parent_sha256": _sha256(parent_path),
        "image": image.to_dict(),
        "capability": capability,
        "candidates": rows,
        "qualified_packages": qualified,
        "selected_package": qualified[0] if qualified else None,
        "integrity": parent["integrity"],
    }
    _write_json_atomic(output, value)
    print(json.dumps({"qualified_packages": qualified}, indent=2, sort_keys=True))
    return 0 if qualified else 1


if __name__ == "__main__":
    raise SystemExit(main())
