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
POLICY_ID = "envsolve-explicit-state-v1"
OUTPUT_PATH = Path("envsolve/protocols/p2_state_freeze_v1.json")
SOURCE_PATHS = (
    Path("envsolve/state/__init__.py"),
    Path("envsolve/state/audit.py"),
    Path("envsolve/state/events.py"),
    Path("envsolve/state/reducer.py"),
    Path("envsolve/state/store.py"),
    Path("envsolve/solver/__init__.py"),
    Path("envsolve/solver/loop.py"),
    Path("envsolve/solver/session.py"),
    Path("envsolve/integrations/__init__.py"),
    Path("envsolve/integrations/shell_trace.py"),
    Path("envsolve/tools/audit_state.py"),
    Path("envsolve/tools/import_shell_trace.py"),
    Path("envsolve/tools/p2_freeze.py"),
    Path("envsolve/tests/test_session.py"),
    Path("research/P2_STATE_PROTOCOL.md"),
)
REAL_ARTIFACT_ROOT = Path(
    "runs/p2-state-recorded-ir-v4-v3/sphinx-scylladb-theme"
)
REAL_CASE_ID = (
    "envbench-python-scylladb__sphinx-scylladb-theme@"
    "4e3917945c5c194a7119cf10629f35664b451d61"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_map(root: Path, paths: tuple[Path, ...]) -> dict[str, str]:
    missing = [str(path) for path in paths if not (root / path).is_file()]
    if missing:
        raise FileNotFoundError(f"P2 freeze source files are missing: {missing}")
    return {str(path): _sha256(root / path) for path in sorted(paths)}


def build_freeze(root: Path, created_at: str) -> dict:
    artifact_root = root / REAL_ARTIFACT_ROOT
    event_log = artifact_root / "state.jsonl"
    snapshot = artifact_root / "snapshot.json"
    audit = audit_state_artifacts(event_log, snapshot, REAL_CASE_ID)
    if not audit.valid:
        raise ValueError(f"P2 validation artifact is invalid: {audit.errors}")
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_id": POLICY_ID,
        "created_at": created_at,
        "source_files": _file_map(root, SOURCE_PATHS),
        "validation": {
            "synthetic_tests": 7,
            "p0_regression_tests": 44,
            "compile_check": True,
            "real_artifact": {
                "root": str(REAL_ARTIFACT_ROOT),
                "case_id": REAL_CASE_ID,
                "event_log_sha256": _sha256(event_log),
                "snapshot_sha256": _sha256(snapshot),
                "event_count": audit.event_count,
                "snapshot_hash": audit.snapshot_hash,
                "audit_valid": audit.valid,
                "actions": 25,
                "action_result_evidence": 25,
                "failures": 1,
            },
        },
        "scope": {
            "p0_scoring_changed": False,
            "model_requests": 0,
            "new_benchmark_cases": 0,
            "canary20_inspected": False,
            "official_test100_inspected": False,
        },
        "change_policy": (
            "Any event, reducer, session, loop, audit, or trace-bridge semantic "
            "change requires a new explicit-state policy and freeze version."
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
        errors.append("P2 source file set or content changed")

    artifact_root = root / REAL_ARTIFACT_ROOT
    event_log = artifact_root / "state.jsonl"
    snapshot = artifact_root / "snapshot.json"
    expected = freeze.get("validation", {}).get("real_artifact", {})
    if not event_log.is_file() or expected.get("event_log_sha256") != _sha256(event_log):
        errors.append("P2 validation event log changed")
    if not snapshot.is_file() or expected.get("snapshot_sha256") != _sha256(snapshot):
        errors.append("P2 validation snapshot changed")
    audit = audit_state_artifacts(event_log, snapshot, REAL_CASE_ID)
    if not audit.valid:
        errors.append("P2 validation artifact audit failed")
    if expected.get("snapshot_hash") != audit.snapshot_hash:
        errors.append("P2 validation snapshot hash changed")
    if expected.get("event_count") != audit.event_count:
        errors.append("P2 validation event count changed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or verify the P2 state freeze.")
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
