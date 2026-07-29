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
from envsolve.runtime.stateful_integrity_v22 import (
    MODULE_IDENTITY_VIOLATION_REASON,
    python_module_identity_audit_command,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Stateful Agent V2.2 module-identity canary."
    )
    parser.add_argument(
        "--image",
        default="ghcr.io/jetbrains-research/envbench-python:latest",
    )
    return parser.parse_args()


def _probe(image: str, project: Path, *, remap: bool) -> dict[str, object]:
    audit = python_module_identity_audit_command("/data/project")
    packages = '["micropy", "micropy.app", "micropy.cli"]' if remap else (
        '["micropy", "micropy.app"]'
    )
    package_dir = (
        '{"": project_root, '
        '"micropy.cli": os.path.join(project_root, "micropy", "app")}'
        if remap
        else '{"": project_root}'
    )
    setup_program = "\n".join(
        (
            "import os",
            "from setuptools import setup",
            'project_root = os.environ["CANARY_PROJECT_ROOT"]',
            'build_root = os.environ["CANARY_BUILD_ROOT"]',
            "setup(",
            '    name="envsolve-module-identity-canary",',
            '    version="0.0.0",',
            f"    packages={packages},",
            f"    package_dir={package_dir},",
            '    options={"egg_info": {"egg_base": build_root}},',
            ")",
        )
    )
    shell = "\n".join(
        (
            "set -e",
            "python3.11 -m venv /tmp/canary-venv",
            ". /tmp/canary-venv/bin/activate",
            "python -m pip install --quiet wheel",
            "build_dir=$(mktemp -d)",
            "cat > \"$build_dir/setup.py\" <<'PY'",
            setup_program,
            "PY",
            (
                "CANARY_PROJECT_ROOT=/data/project "
                "CANARY_BUILD_ROOT=\"$build_dir\" "
                "python -m pip install --no-deps --no-build-isolation "
                "--quiet \"$build_dir\""
            ),
            audit,
        )
    )
    process = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{project}:/data/project:ro",
            image,
            "/bin/bash",
            "--noprofile",
            "--norc",
            "-c",
            shell,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if process.returncode != 0:
        raise RuntimeError(
            "Docker module-identity probe failed: "
            + process.stderr.strip()
        )
    payload = marked_json_payload(process.stdout, IMPORT_ALIAS_AUDIT_MARKER)
    if payload is None:
        raise RuntimeError("Docker module-identity probe returned no audit payload")
    return payload


def main() -> int:
    args = parse_args()
    with tempfile.TemporaryDirectory() as directory:
        project = Path(directory) / "project"
        app = project / "micropy" / "app"
        app.mkdir(parents=True)
        (project / "micropy" / "__init__.py").write_text(
            "from micropy.cli import VALUE\n",
            encoding="utf-8",
        )
        (app / "__init__.py").write_text(
            "VALUE = 'project-app'\n",
            encoding="utf-8",
        )
        declared_result = _probe(args.image, project, remap=False)
        remapped_result = _probe(args.image, project, remap=True)

    remap_reasons = {
        item.get("reason")
        for item in remapped_result.get("violations", [])
        if isinstance(item, dict)
    }
    result = {
        "schema_version": "1.0.0",
        "image": args.image,
        "declared_same_identity_install": declared_result,
        "undeclared_module_identity_remap": remapped_result,
        "passed": (
            declared_result.get("valid") is True
            and remapped_result.get("valid") is False
            and MODULE_IDENTITY_VIOLATION_REASON in remap_reasons
        ),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
