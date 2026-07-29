#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


# ruff: noqa: E402 - workspace path bootstrapping precedes local imports.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.runtime.integrity import (
    IMPORT_ALIAS_AUDIT_MARKER,
    marked_json_payload,
)
from envsolve.runtime.stateful_integrity_v2 import (
    python_source_provenance_audit_command,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Stateful Agent V2 provenance canary in Docker."
    )
    parser.add_argument(
        "--image",
        default="ghcr.io/jetbrains-research/envbench-python:latest",
    )
    return parser.parse_args()


def _probe(image: str, project: Path, external: Path) -> dict[str, object]:
    audit = python_source_provenance_audit_command("/data/project")
    process = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{project}:/data/project:ro",
            "-v",
            f"{external}:/data/external:ro",
            image,
            "/bin/bash",
            "-lc",
            f"export PYTHONPATH=/data/external; {audit}",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if process.returncode != 0:
        raise RuntimeError(
            f"Docker provenance probe failed: {process.stderr.strip()}"
        )
    payload = marked_json_payload(process.stdout, IMPORT_ALIAS_AUDIT_MARKER)
    if payload is None:
        raise RuntimeError("Docker provenance probe returned no audit payload")
    return payload


def main() -> int:
    args = parse_args()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        project = root / "project"
        divergent = root / "divergent"
        identical = root / "identical"
        for package in (
            project / "micropy",
            divergent / "micropy",
            identical / "micropy",
        ):
            package.mkdir(parents=True)
            (package / "__init__.py").write_text(
                "from micropy.cli import VALUE\n",
                encoding="utf-8",
            )
        (divergent / "micropy" / "cli.py").write_text(
            "VALUE = 'old-release'\n",
            encoding="utf-8",
        )

        divergent_result = _probe(args.image, project, divergent)
        identical_result = _probe(args.image, project, identical)

    result = {
        "schema_version": "1.0.0",
        "image": args.image,
        "divergent_external_source": divergent_result,
        "source_identical_external_copy": identical_result,
        "passed": (
            divergent_result.get("valid") is False
            and identical_result.get("valid") is True
        ),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
