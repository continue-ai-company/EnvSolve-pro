#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve.repairs import RepairConstraintEngine, RepairContext, RepairRegistry
from envsolve.state import EventStore, audit_state_artifacts


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def audit_case(item: dict[str, Any]) -> dict[str, Any]:
    case_id = f"recorded-result:{item['repository']}@{item['revision']}"
    artifact_root = WORKSPACE_ROOT / item["artifact_root"]
    event_log = artifact_root / "state.jsonl"
    snapshot = artifact_root / "snapshot.json"
    audit = audit_state_artifacts(event_log, snapshot, case_id)
    if not audit.valid:
        raise ValueError(f"Invalid P3 state artifact for {case_id}: {audit.errors}")
    state = EventStore(event_log, case_id).reconstruct()
    engine = RepairConstraintEngine()
    registry = RepairRegistry()
    context = RepairContext()
    coverage = registry.coverage(state, context, engine)
    plans = registry.propose(state, context, engine)
    return {
        "case_id": case_id,
        "repository": item["repository"],
        "revision": item["revision"],
        "artifact_root": item["artifact_root"],
        "snapshot_hash": audit.snapshot_hash,
        "audit_valid": audit.valid,
        "conflicts": len(engine.solve_state(state).conflicts),
        "coverage": list(coverage),
        "executable_plans": [plan.to_dict() for plan in plans],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit typed-repair coverage on recorded P3 state artifacts."
    )
    parser.add_argument(
        "--p3-summary",
        type=Path,
        default=(
            WORKSPACE_ROOT
            / "experiments/validations/p3_constraint_recorded_dev_results.json"
        ),
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    summary_path = args.p3_summary.resolve()
    p3_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    cases = [audit_case(item) for item in p3_summary["cases"]]
    coverage_rows = [row for case in cases for row in case["coverage"]]
    result = {
        "schema_version": "1.0.0",
        "validation_id": "p4a-recorded-coverage-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "p3_summary": str(summary_path.relative_to(WORKSPACE_ROOT)),
            "p3_summary_sha256": _sha256(summary_path),
            "context": "empty: no unobserved repair context was invented",
        },
        "cases": cases,
        "aggregate": {
            "cases": len(cases),
            "conflicts": sum(int(case["conflicts"]) for case in cases),
            "conflicts_with_operator_family": sum(
                bool(row["operator_kinds"]) for row in coverage_rows
            ),
            "executable_plans": sum(
                len(case["executable_plans"]) for case in cases
            ),
            "audit_valid": all(bool(case["audit_valid"]) for case in cases),
            "model_requests": 0,
            "new_benchmark_executions": 0,
        },
        "integrity": {
            "development_only": True,
            "canary20_inspected": False,
            "official_test100_inspected": False,
            "repository_specific_rules": False,
        },
    }
    _write_json_atomic(args.output.resolve(), result)
    print(json.dumps(result["aggregate"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
