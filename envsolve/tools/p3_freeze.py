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
POLICY_ID = "envsolve-typed-constraints-v1"
OUTPUT_PATH = Path("envsolve/protocols/p3_constraint_freeze_v1.json")
VALIDATION_SUMMARY = Path(
    "experiments/validations/p3_constraint_recorded_dev_results.json"
)
SOURCE_PATHS = (
    Path("envsolve/constraints/__init__.py"),
    Path("envsolve/constraints/engine.py"),
    Path("envsolve/constraints/models.py"),
    Path("envsolve/constraints/normalization.py"),
    Path("envsolve/constraints/policy.py"),
    Path("envsolve/constraints/preflight.py"),
    Path("envsolve/requirements.txt"),
    Path("envsolve/tests/test_constraints.py"),
    Path("envsolve/tools/p3_freeze.py"),
    Path("envsolve/tools/replay_recorded_results.py"),
    Path("research/P3_CONSTRAINT_PROTOCOL.md"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_map(root: Path, paths: tuple[Path, ...]) -> dict[str, str]:
    missing = [str(path) for path in paths if not (root / path).is_file()]
    if missing:
        raise FileNotFoundError(f"P3 freeze source files are missing: {missing}")
    return {str(path): _sha256(root / path) for path in sorted(paths)}


def _validation(root: Path) -> dict:
    summary_path = root / VALIDATION_SUMMARY
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("validation_id") != "p3-recorded-development-v1":
        raise ValueError("Unexpected P3 validation identifier")
    if not summary.get("aggregate", {}).get("audit_valid"):
        raise ValueError("P3 recorded validation is not fully auditable")
    artifacts: list[dict] = []
    for item in summary.get("cases", []):
        artifact_root = root / item["artifact_root"]
        event_log = artifact_root / "state.jsonl"
        snapshot = artifact_root / "snapshot.json"
        case_id = f"recorded-result:{item['repository']}@{item['revision']}"
        audit = audit_state_artifacts(event_log, snapshot, case_id)
        if not audit.valid:
            raise ValueError(f"Invalid P3 artifact for {case_id}: {audit.errors}")
        if audit.event_count != item["event_count"]:
            raise ValueError(f"P3 event count changed for {case_id}")
        if audit.snapshot_hash != item["snapshot_hash"]:
            raise ValueError(f"P3 snapshot hash changed for {case_id}")
        if _sha256(event_log) != item["event_log_sha256"]:
            raise ValueError(f"P3 event log changed for {case_id}")
        if _sha256(snapshot) != item["snapshot_sha256"]:
            raise ValueError(f"P3 snapshot changed for {case_id}")
        source = root / item["source"]
        if _sha256(source) != item["source_sha256"]:
            raise ValueError(f"P3 recorded source changed for {case_id}")
        artifacts.append(
            {
                "case_id": case_id,
                "artifact_root": item["artifact_root"],
                "event_count": audit.event_count,
                "snapshot_hash": audit.snapshot_hash,
                "event_log_sha256": item["event_log_sha256"],
                "snapshot_sha256": item["snapshot_sha256"],
                "source": item["source"],
                "source_sha256": item["source_sha256"],
                "constraints": item["constraints"],
                "conflicts": len(item["report"]["conflicts"]),
                "audit_valid": audit.valid,
            }
        )
    return {
        "summary": str(VALIDATION_SUMMARY),
        "summary_sha256": _sha256(summary_path),
        "aggregate": summary["aggregate"],
        "artifacts": artifacts,
    }


def build_freeze(root: Path, created_at: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_id": POLICY_ID,
        "created_at": created_at,
        "source_files": _file_map(root, SOURCE_PATHS),
        "validation": {
            "synthetic_tests": 17,
            "p2_regression_tests": 7,
            "p0_regression_tests": 44,
            "compile_check": True,
            "recorded_development": _validation(root),
        },
        "semantics": {
            "hard_confidence": 0.8,
            "dispositions": ["allow", "require_evidence", "reject"],
            "constraint_schema": "1.0.0",
            "pep440_library": "packaging>=24,<27",
        },
        "scope": {
            "p0_scoring_changed": False,
            "p2_semantics_changed": False,
            "model_requests": 0,
            "new_benchmark_executions": 0,
            "new_benchmark_cases": 0,
            "canary20_inspected": False,
            "official_test100_inspected": False,
            "solver_case_specific_rules": False,
        },
        "change_policy": (
            "Any normalized constraint schema, confidence threshold, propagation, "
            "conflict, or preflight semantic change requires a new P3 policy and "
            "freeze version."
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
        errors.append("P3 source file set or content changed")
    try:
        current_validation = _validation(root)
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        errors.append(f"P3 validation failed: {type(exc).__name__}: {exc}")
        current_validation = None
    expected = freeze.get("validation", {}).get("recorded_development")
    if current_validation is not None and expected != current_validation:
        errors.append("P3 recorded validation changed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify the P3 constraint freeze."
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
