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

from envsolve.constraints import ConstraintEngine
from envsolve.solver import SolverStateSession
from envsolve.state import audit_state_artifacts


DIAGNOSTIC_TAIL_LIMIT = 16_000


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slug(value: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in value)


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


def replay_result(result_path: Path, output_root: Path) -> dict[str, Any]:
    raw = json.loads(result_path.read_text(encoding="utf-8"))
    repository = str(raw["repo_name"])
    revision = str(raw["commit_sha"])
    logs = str(raw.get("container_logs", ""))
    case_id = f"recorded-result:{repository}@{revision}"
    artifact_root = output_root / _slug(f"{repository}-{revision[:12]}")
    event_log = artifact_root / "state.jsonl"
    snapshot = artifact_root / "snapshot.json"
    if event_log.exists() or snapshot.exists():
        raise FileExistsError(f"Refusing to overwrite validation artifact: {artifact_root}")

    session = SolverStateSession(
        event_log,
        snapshot,
        {
            "case_id": case_id,
            "repository": repository,
            "revision": revision,
            "language": "python",
            "split": "development-consumed",
            "tags": ["recorded-result", "p3-validation"],
        },
    )
    source_hash = _sha256(result_path)
    diagnostic_tail = logs[-DIAGNOSTIC_TAIL_LIMIT:]
    session.record_evidence(
        kind="action-result",
        source=f"recorded-json:{result_path.name}:sha256:{source_hash}",
        value={
            "exit_code": int(raw.get("exit_code", 1)),
            "stdout": "",
            "stderr": diagnostic_tail,
            "capture": "tail",
            "original_characters": len(logs),
        },
    )
    report = ConstraintEngine().propagate(session)
    audit = audit_state_artifacts(event_log, snapshot, case_id)
    if not audit.valid:
        raise ValueError(f"Recorded validation artifact failed audit: {audit.errors}")
    state = session.reconstruct()
    return {
        "repository": repository,
        "revision": revision,
        "source": str(result_path.relative_to(WORKSPACE_ROOT)),
        "source_sha256": source_hash,
        "source_log_characters": len(logs),
        "diagnostic_tail_sha256": hashlib.sha256(
            diagnostic_tail.encode("utf-8")
        ).hexdigest(),
        "artifact_root": str(artifact_root.relative_to(WORKSPACE_ROOT)),
        "event_count": audit.event_count,
        "snapshot_hash": audit.snapshot_hash,
        "snapshot_sha256": _sha256(snapshot),
        "event_log_sha256": _sha256(event_log),
        "audit_valid": audit.valid,
        "constraints": len(state.constraints),
        "report": report.to_dict(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay recorded command-result JSON through the P3 constraint engine."
    )
    parser.add_argument("--result", action="append", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    args = parser.parse_args()
    results = [
        replay_result(path.resolve(), args.output_root.resolve())
        for path in args.result
    ]
    summary = {
        "schema_version": "1.0.0",
        "validation_id": "p3-recorded-development-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "adapter": {
            "input": "recorded command-result JSON",
            "capture": "last 16000 characters of container output",
            "core_benchmark_specific": False,
        },
        "cases": results,
        "aggregate": {
            "cases": len(results),
            "audit_valid": all(item["audit_valid"] for item in results),
            "constraints": sum(int(item["constraints"]) for item in results),
            "conflicts": sum(len(item["report"]["conflicts"]) for item in results),
            "model_requests": 0,
            "new_benchmark_executions": 0,
        },
        "integrity": {
            "split": "development-consumed",
            "canary20_inspected": False,
            "official_test100_inspected": False,
            "solver_case_specific_rules": False,
        },
    }
    _write_json_atomic(args.summary.resolve(), summary)
    print(json.dumps(summary["aggregate"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
