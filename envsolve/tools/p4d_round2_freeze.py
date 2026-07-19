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
POLICY_ID = "envsolve-p4d-capability-round2-v1"
OUTPUT_PATH = Path("envsolve/protocols/p4d_capability_round2_freeze_v1.json")
RESULT_PATH = Path("experiments/validations/p4d_capability_round2_results.json")
SOURCE_PATHS = (
    Path("envsolve/discovery/packages_policy.py"),
    Path("envsolve/discovery/ubuntu_packages.py"),
    Path("envsolve/tests/test_ubuntu_packages_discovery.py"),
    Path("envsolve/tools/p4d_round2_freeze.py"),
    Path("envsolve/tools/run_p4d_capability_round2.py"),
    Path("experiments/validations/p4d_capability_round2_preregistration.json"),
    Path("research/P4D_CAPABILITY_DISCOVERY_ROUND2_PROTOCOL.md"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_map(root: Path) -> dict[str, str]:
    missing = [str(path) for path in SOURCE_PATHS if not (root / path).is_file()]
    if missing:
        raise FileNotFoundError(f"P4D Round 2 source files are missing: {missing}")
    return {str(path): _sha256(root / path) for path in sorted(SOURCE_PATHS)}


def _validation(root: Path) -> dict:
    path = root / RESULT_PATH
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("validation_id") != "p4d-capability-round2-v1":
        raise ValueError("Unexpected P4D Round 2 validation identifier")
    discovery = value["discovery"]
    if (
        discovery["goal_status"] != "satisfied"
        or discovery["actions_executed"] != 5
        or discovery["actions_failed"] != 0
    ):
        raise ValueError("P4D Round 2 discovery result changed")
    commands = [plan["mutation_command"] for plan in value["plans"]]
    if commands != [
        "apt-get install -y -- postgresql-common",
        "apt-get install -y -- libpq-dev",
    ]:
        raise ValueError("P4D Round 2 candidate plans changed")
    repairs = value["repair_results"]
    if len(repairs) != 1 or repairs[0]["execution"]["goal_status"] != "satisfied":
        raise ValueError("P4D Round 2 V1 repair result changed")
    if value["post_state"]["satisfiable"] is not True:
        raise ValueError("P4D Round 2 typed state is no longer satisfiable")
    if value["superseded_constraint_ids"] != [
        "constraint-capability-7d7a75f5f64b44eb",
        "constraint-capability-7d7a75f5f64b44eb",
    ]:
        raise ValueError("P4D Round 2 disclosed summary signature changed")
    artifact = value["artifact"]
    artifact_root = root / artifact["root"]
    event_log = artifact_root / "state.jsonl"
    snapshot = artifact_root / "snapshot.json"
    plan = artifact_root / "repair_plans.json"
    audit = audit_state_artifacts(event_log, snapshot, artifact["case_id"])
    if not audit.valid or audit.event_count != 55:
        raise ValueError("P4D Round 2 artifact failed audit")
    if audit.snapshot_hash != artifact["snapshot_hash"]:
        raise ValueError("P4D Round 2 snapshot hash changed")
    if (
        _sha256(event_log) != artifact["event_log_sha256"]
        or _sha256(snapshot) != artifact["snapshot_sha256"]
        or _sha256(plan) != artifact["plan_sha256"]
    ):
        raise ValueError("P4D Round 2 artifact content changed")
    state = json.loads(snapshot.read_text(encoding="utf-8"))
    verifications = state.get("verifications", [])
    if len(verifications) != 1 or verifications[0].get("passed") is not True:
        raise ValueError("P4D Round 2 lacks its passing V1 verification")
    return {
        "path": str(RESULT_PATH),
        "sha256": _sha256(path),
        "discovery": discovery,
        "plans": value["plans"],
        "repair_results": repairs,
        "post_state": value["post_state"],
        "artifact": artifact,
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
            "synthetic_tests": 3,
            "compile_check": True,
            "v1_presence_transition": _validation(root),
        },
        "finding": {
            "provider_discovery_satisfied": True,
            "candidate_count": 2,
            "selected_package": "postgresql-common",
            "v1_presence_verified": True,
            "semantic_interface_verified": False,
            "semantic_interface_status": "not-yet-tested",
            "candidate_order": "repair-id",
            "disclosed_duplicate_summary_ids": True,
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
            "Round 2 source and V1 transition artifacts are immutable. A semantic "
            "capability verifier or candidate selector requires a new round."
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
        errors.append("P4D Round 2 source file set or content changed")
    try:
        validation = _validation(root)
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        errors.append(f"P4D Round 2 validation failed: {type(exc).__name__}: {exc}")
        validation = None
    expected = freeze.get("validation", {}).get("v1_presence_transition")
    if validation is not None and validation != expected:
        errors.append("P4D Round 2 validation changed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify the P4D Round 2 freeze."
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
