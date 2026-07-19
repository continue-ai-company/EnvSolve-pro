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
POLICY_ID = "envsolve-typed-repair-kernel-v1"
OUTPUT_PATH = Path("envsolve/protocols/p4a_repair_freeze_v1.json")
VALIDATION_PATH = Path("experiments/validations/p4a_recorded_coverage.json")
SOURCE_PATHS = (
    Path("envsolve/repairs/__init__.py"),
    Path("envsolve/repairs/engine.py"),
    Path("envsolve/repairs/models.py"),
    Path("envsolve/repairs/operators.py"),
    Path("envsolve/repairs/policy.py"),
    Path("envsolve/tests/test_repairs.py"),
    Path("envsolve/tools/audit_repair_coverage.py"),
    Path("envsolve/tools/p4a_freeze.py"),
    Path("research/P4_TYPED_REPAIR_PROTOCOL.md"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_map(root: Path, paths: tuple[Path, ...]) -> dict[str, str]:
    missing = [str(path) for path in paths if not (root / path).is_file()]
    if missing:
        raise FileNotFoundError(f"P4A freeze source files are missing: {missing}")
    return {str(path): _sha256(root / path) for path in sorted(paths)}


def _validation(root: Path) -> dict:
    path = root / VALIDATION_PATH
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("validation_id") != "p4a-recorded-coverage-v1":
        raise ValueError("Unexpected P4A validation identifier")
    aggregate = value.get("aggregate", {})
    expected = {
        "cases": 2,
        "conflicts": 2,
        "conflicts_with_operator_family": 2,
        "executable_plans": 0,
        "audit_valid": True,
        "model_requests": 0,
        "new_benchmark_executions": 0,
    }
    if aggregate != expected:
        raise ValueError(f"Unexpected P4A validation aggregate: {aggregate}")
    p3_summary = root / value["input"]["p3_summary"]
    if _sha256(p3_summary) != value["input"]["p3_summary_sha256"]:
        raise ValueError("P4A input P3 summary changed")
    cases: list[dict] = []
    for item in value["cases"]:
        artifact_root = root / item["artifact_root"]
        case_id = str(item["case_id"])
        audit = audit_state_artifacts(
            artifact_root / "state.jsonl",
            artifact_root / "snapshot.json",
            case_id,
        )
        if not audit.valid or audit.snapshot_hash != item["snapshot_hash"]:
            raise ValueError(f"P4A source state audit failed for {case_id}")
        if item["executable_plans"]:
            raise ValueError(f"P4A recorded audit invented a plan for {case_id}")
        cases.append(
            {
                "case_id": case_id,
                "artifact_root": item["artifact_root"],
                "snapshot_hash": audit.snapshot_hash,
                "conflicts": item["conflicts"],
                "coverage": item["coverage"],
                "executable_plans": 0,
                "audit_valid": audit.valid,
            }
        )
    return {
        "path": str(VALIDATION_PATH),
        "sha256": _sha256(path),
        "aggregate": aggregate,
        "cases": cases,
    }


def build_freeze(root: Path, created_at: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_id": POLICY_ID,
        "created_at": created_at,
        "source_files": _file_map(root, SOURCE_PATHS),
        "validation": {
            "synthetic_tests": 13,
            "p3_regression_tests": 17,
            "p2_regression_tests": 7,
            "p0_regression_tests": 44,
            "compile_check": True,
            "recorded_coverage": _validation(root),
        },
        "semantics": {
            "operator_families": [
                "runtime_selection",
                "system_capability_install",
                "python_module_install",
            ],
            "commit_gate": "independent_probe_observes_proposed_fact",
            "requirements_supersedable": False,
            "context_requires_evidence": True,
        },
        "scope": {
            "p0_scoring_changed": False,
            "p2_semantics_changed": False,
            "p3_semantics_changed": False,
            "model_requests": 0,
            "new_benchmark_executions": 0,
            "new_benchmark_cases": 0,
            "canary20_inspected": False,
            "official_test100_inspected": False,
            "repository_specific_rules": False,
            "p4_complete": False,
        },
        "change_policy": (
            "Any repair schema, operator selection, transition preflight, probe "
            "parser, or verification-gated commit semantic change requires a new "
            "P4A policy and freeze version."
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
        errors.append("P4A source file set or content changed")
    try:
        current_validation = _validation(root)
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        errors.append(f"P4A validation failed: {type(exc).__name__}: {exc}")
        current_validation = None
    expected = freeze.get("validation", {}).get("recorded_coverage")
    if current_validation is not None and expected != current_validation:
        errors.append("P4A recorded coverage changed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify the P4A typed-repair freeze."
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
