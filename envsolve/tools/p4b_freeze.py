#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve.state import audit_state_artifacts


SCHEMA_VERSION = "1.0.0"
POLICY_ID = "envsolve-context-acquisition-v1"
OUTPUT_PATH = Path("envsolve/protocols/p4b_context_freeze_v1.json")
VALIDATION_PATH = Path("experiments/validations/p4b_context_image_results.json")
SOURCE_PATHS = (
    Path("envsolve/context/__init__.py"),
    Path("envsolve/context/builder.py"),
    Path("envsolve/context/models.py"),
    Path("envsolve/context/policy.py"),
    Path("envsolve/context/probes.py"),
    Path("envsolve/context/providers.py"),
    Path("envsolve/tests/test_context.py"),
    Path("envsolve/tools/p4b_freeze.py"),
    Path("envsolve/tools/run_context_image_inventory.py"),
    Path("research/P4B_CONTEXT_ACQUISITION_PROTOCOL.md"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_map(root: Path, paths: tuple[Path, ...]) -> dict[str, str]:
    missing = [str(path) for path in paths if not (root / path).is_file()]
    if missing:
        raise FileNotFoundError(f"P4B freeze source files are missing: {missing}")
    return {str(path): _sha256(root / path) for path in sorted(paths)}


def _local_image_id(reference: str) -> str:
    process = subprocess.run(
        ["docker", "image", "inspect", reference, "--format", "{{.Id}}"],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if process.returncode != 0:
        raise ValueError(process.stderr.strip() or "evaluator image inspect failed")
    return process.stdout.strip()


def _validation(root: Path) -> dict:
    path = root / VALIDATION_PATH
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("validation_id") != "p4b-case-free-image-context-v1":
        raise ValueError("Unexpected P4B validation identifier")
    result = value.get("result", {})
    if result.get("goal_status") != "satisfied":
        raise ValueError("P4B context acquisition did not satisfy its goal")
    if (
        result.get("actions_executed") != 7
        or result.get("actions_succeeded") != 7
        or result.get("actions_failed") != 0
    ):
        raise ValueError(f"Unexpected P4B action result: {result}")
    isolation = value.get("isolation", {})
    if isolation != {
        "benchmark_repository_mounted": False,
        "mounts": [],
        "network": "none",
    }:
        raise ValueError(f"Unexpected P4B isolation record: {isolation}")
    context = value.get("context", {}).get("context", {})
    expected_versions = [
        "3.8.18",
        "3.9.18",
        "3.10.13",
        "3.11.7",
        "3.12.0",
        "3.13.1",
    ]
    if (
        context.get("runtime_manager") != "pyenv"
        or context.get("system_package_manager") != "apt-get"
        or context.get("available_python_versions") != expected_versions
        or context.get("capability_packages") != {}
        or context.get("module_distributions") != {}
    ):
        raise ValueError(f"Unexpected P4B derived context: {context}")
    image = value.get("image", {})
    if _local_image_id(str(image.get("reference"))) != image.get("id"):
        raise ValueError("P4B evaluator image identity changed")
    artifact = value.get("artifact", {})
    artifact_root = root / artifact["root"]
    event_log = artifact_root / "state.jsonl"
    snapshot = artifact_root / "snapshot.json"
    audit = audit_state_artifacts(event_log, snapshot, artifact["case_id"])
    if not audit.valid:
        raise ValueError(f"P4B context artifact audit failed: {audit.errors}")
    if audit.event_count != 39 or audit.event_count != artifact["event_count"]:
        raise ValueError("P4B context event count changed")
    if audit.snapshot_hash != artifact["snapshot_hash"]:
        raise ValueError("P4B context snapshot hash changed")
    if _sha256(event_log) != artifact["event_log_sha256"]:
        raise ValueError("P4B context event log changed")
    if _sha256(snapshot) != artifact["snapshot_sha256"]:
        raise ValueError("P4B context snapshot changed")
    snapshot_value = json.loads(snapshot.read_text(encoding="utf-8"))
    if snapshot_value.get("failures"):
        raise ValueError("P4B context artifact contains failures")
    return {
        "path": str(VALIDATION_PATH),
        "sha256": _sha256(path),
        "image": image,
        "isolation": isolation,
        "result": result,
        "context": context,
        "artifact": artifact,
    }


def build_freeze(root: Path, created_at: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_id": POLICY_ID,
        "created_at": created_at,
        "source_files": _file_map(root, SOURCE_PATHS),
        "validation": {
            "synthetic_tests": 11,
            "p4a_regression_tests": 13,
            "p3_regression_tests": 17,
            "p2_regression_tests": 7,
            "p0_regression_tests": 44,
            "compile_check": True,
            "case_free_image_inventory": _validation(root),
        },
        "semantics": {
            "hard_confidence": 0.8,
            "system_manager_priority": ["apt-get", "apk", "dnf", "yum", "brew"],
            "optional_missing_tools_are_failures": False,
            "context_fields_require_evidence": True,
            "capability_provider": "apt-file-exact-path-v1",
        },
        "scope": {
            "p0_scoring_changed": False,
            "p2_semantics_changed": False,
            "p3_semantics_changed": False,
            "p4a_semantics_changed": False,
            "model_requests": 0,
            "new_benchmark_executions": 0,
            "new_benchmark_cases": 0,
            "canary20_inspected": False,
            "official_test100_inspected": False,
            "repository_specific_rules": False,
            "p4_complete": False,
        },
        "change_policy": (
            "Any context evidence schema, confidence gate, probe command/parser, "
            "manager priority, context builder, or provider parser semantic change "
            "requires a new P4B policy and freeze version."
        ),
    }


def verify_freeze(root: Path, freeze: dict) -> list[str]:
    errors: list[str] = []
    if freeze.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema version mismatch")
    if freeze.get("policy_id") != POLICY_ID:
        errors.append("policy identifier mismatch")
    try:
        current_files = _file_map(root, SOURCE_PATHS)
    except FileNotFoundError as exc:
        errors.append(str(exc))
        current_files = {}
    if freeze.get("source_files") != current_files:
        errors.append("P4B source file set or content changed")
    try:
        current_validation = _validation(root)
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        errors.append(f"P4B validation failed: {type(exc).__name__}: {exc}")
        current_validation = None
    expected = freeze.get("validation", {}).get("case_free_image_inventory")
    if current_validation is not None and expected != current_validation:
        errors.append("P4B case-free image validation changed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify the P4B context-acquisition freeze."
    )
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--output", type=Path, default=WORKSPACE_ROOT / OUTPUT_PATH)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.verify:
        freeze = json.loads(output.read_text(encoding="utf-8"))
        errors = verify_freeze(WORKSPACE_ROOT, freeze)
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
        return 0 if not errors else 1
    output.parent.mkdir(parents=True, exist_ok=True)
    freeze = build_freeze(
        WORKSPACE_ROOT,
        datetime.now(timezone.utc).isoformat(),
    )
    output.write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
