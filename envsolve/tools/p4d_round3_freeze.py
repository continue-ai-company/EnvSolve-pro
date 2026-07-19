#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.state import audit_state_artifacts


OUTPUT = Path("envsolve/protocols/p4d_capability_round3_freeze_v1.json")
QUALIFICATION = Path("experiments/validations/p4d_capability_round3_qualification.json")
RETRY = Path("experiments/validations/p4d_capability_round3_retry_results.json")
REPAIR = Path("experiments/validations/p4d_capability_round3_repair_results.json")
SOURCES = (
    Path("envsolve/verification/__init__.py"),
    Path("envsolve/verification/capability.py"),
    Path("envsolve/tests/test_semantic_capability.py"),
    Path("envsolve/tools/p4d_round3_freeze.py"),
    Path("envsolve/tools/run_p4d_round3_qualification.py"),
    Path("envsolve/tools/run_p4d_round3_retry.py"),
    Path("envsolve/tools/run_p4d_round3_repair.py"),
    Path("experiments/validations/p4d_capability_round3_preregistration.json"),
    Path("experiments/validations/p4d_capability_round3_retry_preregistration.json"),
    Path("experiments/validations/p4d_capability_round3_repair_preregistration.json"),
    Path("research/P4D_CAPABILITY_DISCOVERY_ROUND3_PROTOCOL.md"),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files() -> dict[str, str]:
    missing = [str(path) for path in SOURCES if not (ROOT / path).is_file()]
    if missing:
        raise FileNotFoundError(f"P4D Round 3 source files are missing: {missing}")
    return {str(path): sha(ROOT / path) for path in sorted(SOURCES)}


def validation() -> dict:
    qualification = json.loads((ROOT / QUALIFICATION).read_text(encoding="utf-8"))
    retry = json.loads((ROOT / RETRY).read_text(encoding="utf-8"))
    repair = json.loads((ROOT / REPAIR).read_text(encoding="utf-8"))
    rows = {item["package"]: item for item in qualification["candidates"]}
    if (
        rows["postgresql-common"]["results"][-1]["exit_code"] != 1
        or rows["postgresql-common"]["qualified"] is not False
        or rows["libpq-dev"]["results"][0]["exit_code"] != 124
    ):
        raise ValueError("Round 3 initial qualification signature changed")
    if retry.get("qualified_packages") != ["libpq-dev"]:
        raise ValueError("Round 3 retry qualification changed")
    if (
        repair.get("validation_id") != "p4d-capability-round3-repair-v1"
        or repair["execution"]["goal_status"] != "satisfied"
        or repair["post_state"]["satisfiable"] is not True
        or repair["selected_package"] != "libpq-dev"
        or repair["superseded_constraint_ids"]
        != ["constraint-capability-7d7a75f5f64b44eb"]
    ):
        raise ValueError("Round 3 V2 repair result changed")
    verifications = repair["verifications"]
    if len(verifications) != 1 or verifications[0]["level"] != "V2" or not verifications[0]["passed"]:
        raise ValueError("Round 3 lacks its passing V2 verification")
    artifact = repair["artifact"]
    artifact_root = ROOT / artifact["root"]
    event_log = artifact_root / "state.jsonl"
    snapshot = artifact_root / "snapshot.json"
    plan = artifact_root / "repair_plan.json"
    audit = audit_state_artifacts(event_log, snapshot, artifact["case_id"])
    if not audit.valid or audit.snapshot_hash != artifact["snapshot_hash"]:
        raise ValueError("Round 3 repair artifact failed audit")
    if (
        sha(event_log) != artifact["event_log_sha256"]
        or sha(snapshot) != artifact["snapshot_sha256"]
        or sha(plan) != artifact["plan_sha256"]
    ):
        raise ValueError("Round 3 repair artifact content changed")
    return {
        "qualification": {"path": str(QUALIFICATION), "sha256": sha(ROOT / QUALIFICATION)},
        "retry": {"path": str(RETRY), "sha256": sha(ROOT / RETRY)},
        "repair": {
            "path": str(REPAIR),
            "sha256": sha(ROOT / REPAIR),
            "execution": repair["execution"],
            "post_state": repair["post_state"],
            "artifact": artifact,
            "selected_package": repair["selected_package"],
            "superseded_constraint_ids": repair["superseded_constraint_ids"],
        },
    }


def build(created_at: str) -> dict:
    return {
        "schema_version": "1.0.0",
        "policy_id": "envsolve-p4d-semantic-capability-v2",
        "created_at": created_at,
        "source_files": files(),
        "validation": {
            "semantic_policy_tests": 2,
            "compile_check": True,
            "trajectories": validation(),
        },
        "finding": {
            "v1_false_success_package": "postgresql-common",
            "v1_presence_passed": True,
            "v2_semantic_passed": False,
            "qualified_package": "libpq-dev",
            "final_v2_transition_satisfied": True,
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
    }


def verify(value: dict) -> list[str]:
    errors = []
    if value.get("schema_version") != "1.0.0":
        errors.append("schema version mismatch")
    if value.get("policy_id") != "envsolve-p4d-semantic-capability-v2":
        errors.append("policy identifier mismatch")
    try:
        current_files = files()
    except FileNotFoundError as exc:
        errors.append(str(exc))
        current_files = {}
    if value.get("source_files") != current_files:
        errors.append("Round 3 source files changed")
    try:
        current_validation = validation()
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        errors.append(f"Round 3 validation failed: {type(exc).__name__}: {exc}")
        current_validation = None
    if current_validation is not None and value.get("validation", {}).get("trajectories") != current_validation:
        errors.append("Round 3 validation changed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or verify the P4D Round 3 freeze.")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.verify:
        errors = verify(json.loads(output.read_text(encoding="utf-8")))
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
        return 0 if not errors else 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build(datetime.now(timezone.utc).isoformat()), indent=2, sort_keys=True) + "\n"
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
