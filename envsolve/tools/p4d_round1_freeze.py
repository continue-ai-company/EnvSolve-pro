#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve.state import audit_state_artifacts


SCHEMA_VERSION = "1.0.0"
POLICY_ID = "envsolve-p4d-capability-round1-v1"
OUTPUT_PATH = Path("envsolve/protocols/p4d_capability_round1_freeze_v1.json")
RESULT_PATH = Path("experiments/validations/p4d_capability_round1_results.json")
SOURCE_PATHS = (
    Path("envsolve/discovery/__init__.py"),
    Path("envsolve/discovery/apt_file.py"),
    Path("envsolve/discovery/policy.py"),
    Path("envsolve/tests/test_capability_discovery.py"),
    Path("envsolve/tools/p4d_round1_freeze.py"),
    Path("envsolve/tools/run_p4d_capability_validation.py"),
    Path("experiments/validations/p4d_capability_round1_preregistration.json"),
    Path("research/P4D_CAPABILITY_DISCOVERY_PROTOCOL.md"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_map(root: Path) -> dict[str, str]:
    missing = [str(path) for path in SOURCE_PATHS if not (root / path).is_file()]
    if missing:
        raise FileNotFoundError(f"P4D Round 1 source files are missing: {missing}")
    return {str(path): _sha256(root / path) for path in sorted(SOURCE_PATHS)}


def _validation(root: Path) -> dict:
    path = root / RESULT_PATH
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("validation_id") != "p4d-capability-round1-v1":
        raise ValueError("Unexpected P4D Round 1 validation identifier")
    discovery = value.get("discovery", {})
    if discovery != {
        "actions_executed": 7,
        "actions_failed": 1,
        "actions_succeeded": 6,
        "goal_status": "blocked",
        "snapshot_hash": value["artifact"]["snapshot_hash"],
        "stop_reason": "Provider action discovery-pg_config-index-update did not succeed",
    }:
        raise ValueError("P4D Round 1 failure signature changed")
    if value.get("plans") or value.get("repair_results"):
        raise ValueError("P4D Round 1 unexpectedly contains a repair attempt")
    if value.get("superseded_constraint_ids"):
        raise ValueError("P4D Round 1 superseded an unverified fact")
    if value.get("post_state", {}).get("satisfiable") is not False:
        raise ValueError("P4D Round 1 unexpectedly became satisfiable")
    if value.get("isolation") != {
        "mounts": [],
        "network": "bridge",
        "network_purpose": "apt provider and package acquisition",
        "official_evaluation": False,
        "repository_mounted": False,
    }:
        raise ValueError("P4D Round 1 isolation record changed")
    artifact = value["artifact"]
    artifact_root = root / artifact["root"]
    event_log = artifact_root / "state.jsonl"
    snapshot = artifact_root / "snapshot.json"
    audit = audit_state_artifacts(event_log, snapshot, artifact["case_id"])
    if not audit.valid or audit.event_count != 46:
        raise ValueError("P4D Round 1 artifact failed audit")
    if audit.snapshot_hash != artifact["snapshot_hash"]:
        raise ValueError("P4D Round 1 snapshot hash changed")
    if (
        _sha256(event_log) != artifact["event_log_sha256"]
        or _sha256(snapshot) != artifact["snapshot_sha256"]
        or artifact.get("plan_sha256") is not None
    ):
        raise ValueError("P4D Round 1 artifact content changed")
    state = json.loads(snapshot.read_text(encoding="utf-8"))
    timed_out = state["actions"].get("discovery-pg_config-index-update", {})
    if timed_out.get("exit_code") != 124:
        raise ValueError("P4D Round 1 no longer records the provider timeout")
    return {
        "path": str(RESULT_PATH),
        "sha256": _sha256(path),
        "discovery": discovery,
        "post_state": value["post_state"],
        "artifact": artifact,
        "commands": value["commands"],
        "image": value["image"],
        "isolation": value["isolation"],
        "integrity": value["integrity"],
    }


def build_freeze(root: Path, created_at: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_id": POLICY_ID,
        "created_at": created_at,
        "source_files": _file_map(root),
        "validation": {
            "synthetic_tests": 4,
            "compile_check": True,
            "provider_blocked_trajectory": _validation(root),
        },
        "finding": {
            "stage": "provider-index-update",
            "failure": "hard-timeout",
            "timeout_seconds": 600,
            "repair_attempted": False,
            "fact_superseded": False,
        },
        "scope": {
            "development_only": True,
            "model_requests": 0,
            "new_benchmark_executions": 0,
            "canary20_inspected": False,
            "official_test100_inspected": False,
            "repository_specific_rules": False,
            "p4_complete": False,
        },
        "change_policy": (
            "Round 1 source and failure artifacts are immutable. Any provider "
            "acquisition or candidate-selection change requires a new round."
        ),
    }


def verify_freeze(root: Path, freeze: dict) -> list[str]:
    errors: list[str] = []
    if freeze.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema version mismatch")
    if freeze.get("policy_id") != POLICY_ID:
        errors.append("policy identifier mismatch")
    try:
        files = _file_map(root)
    except FileNotFoundError as exc:
        errors.append(str(exc))
        files = {}
    if freeze.get("source_files") != files:
        errors.append("P4D Round 1 source file set or content changed")
    try:
        validation = _validation(root)
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        errors.append(f"P4D Round 1 validation failed: {type(exc).__name__}: {exc}")
        validation = None
    expected = freeze.get("validation", {}).get("provider_blocked_trajectory")
    if validation is not None and validation != expected:
        errors.append("P4D Round 1 validation changed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify the P4D Round 1 freeze."
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
    freeze = build_freeze(WORKSPACE_ROOT, datetime.now(timezone.utc).isoformat())
    output.write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
