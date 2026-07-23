#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.state import EventStore
from envsolve.state.events import EventType
from envsolve_harness.core.io import write_json
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.utils.provenance import sha256_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit persisted model-visible causal-frontier projections."
    )
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--required-model-projection-schema")
    parser.add_argument("--require-complete-roots", action="store_true")
    return parser.parse_args()


def _canonical_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def audit_snapshot(
    metadata: object,
    required_model_projection_schema: str | None = None,
    require_complete_roots: bool = False,
) -> dict[str, Any]:
    value = metadata if isinstance(metadata, dict) else {}
    snapshot = value.get("constraint_frontier_snapshot")
    expected_hash = value.get("constraint_frontier_sha256")
    reasons: list[str] = []
    if not isinstance(snapshot, dict):
        return {
            "integrity_ok": False,
            "failure_reasons": ["snapshot_missing_or_not_object"],
            "hash_valid": False,
            "whole_object_truncated": False,
            "causal_roots_count": None,
        }

    observed_hash = _canonical_hash(snapshot)
    hash_valid = isinstance(expected_hash, str) and observed_hash == expected_hash
    whole_object_truncated = snapshot.get("truncated") is True
    roots = snapshot.get("causal_roots")
    summary = snapshot.get("summary")
    model_projection_schema = snapshot.get("model_projection_schema_version")
    if not hash_valid:
        reasons.append("persisted_hash_missing_or_invalid")
    if whole_object_truncated:
        reasons.append("whole_object_truncated")
    if not isinstance(roots, list):
        reasons.append("causal_roots_missing_or_not_list")
    if not isinstance(summary, dict):
        reasons.append("summary_missing_or_not_object")
    if (
        required_model_projection_schema is not None
        and model_projection_schema != required_model_projection_schema
    ):
        reasons.append("model_projection_schema_mismatch")
    if (
        require_complete_roots
        and isinstance(summary, dict)
        and summary.get("causal_roots_omitted") != 0
    ):
        reasons.append("causal_roots_incomplete")
    return {
        "integrity_ok": not reasons,
        "failure_reasons": reasons,
        "hash_valid": hash_valid,
        "whole_object_truncated": whole_object_truncated,
        "causal_roots_count": len(roots) if isinstance(roots, list) else None,
        "model_projection_schema_version": model_projection_schema,
    }


def audit_episode(
    episode: dict[str, Any],
    runs_root: Path,
    required_model_projection_schema: str | None = None,
    require_complete_roots: bool = False,
) -> dict[str, Any]:
    case_id = str(episode["case_id"])
    case_root = runs_root / safe_name(str(episode["run_id"])) / safe_name(case_id)
    trajectory = case_root / "generation" / "episode.jsonl"
    decisions = []
    for event in EventStore(trajectory, case_id).read():
        if event.event_type != EventType.ACTION_PROPOSED.value:
            continue
        decision = audit_snapshot(
            event.payload.get("metadata"),
            required_model_projection_schema,
            require_complete_roots,
        )
        decisions.append(
            {
                "candidate_id": event.payload["action_id"],
                "event_sequence": event.sequence,
                **decision,
            }
        )
    integrity_ok = bool(decisions) and all(
        item["integrity_ok"] for item in decisions
    )
    return {
        "position": episode["position"],
        "pair": episode["pair"],
        "condition": episode["condition"],
        "case_id": case_id,
        "run_id": episode["run_id"],
        "trajectory_sha256": sha256_file(trajectory),
        "decision_count": len(decisions),
        "projection_integrity_ok": integrity_ok,
        "invalid_decision_count": sum(
            not item["integrity_ok"] for item in decisions
        ),
        "decisions": decisions,
    }


def aggregate(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    causal = [item for item in episodes if item["condition"] == "causal-frontier"]
    decision_count = sum(int(item["decision_count"]) for item in causal)
    invalid_count = sum(int(item["invalid_decision_count"]) for item in causal)
    integrity_ok = bool(causal) and decision_count > 0 and invalid_count == 0
    reasons = sorted(
        {
            reason
            for episode in causal
            for decision in episode["decisions"]
            for reason in decision["failure_reasons"]
        }
    )
    return {
        "causal_episode_count": len(causal),
        "causal_decision_count": decision_count,
        "invalid_causal_decision_count": invalid_count,
        "measurement_integrity_ok": integrity_ok,
        "effect_analysis_admissible": integrity_ok,
        "failure_reasons": reasons,
    }


def main() -> int:
    args = parse_args()
    schedule_path = args.schedule.resolve()
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    episodes = [
        audit_episode(
            episode,
            args.runs_root.resolve(),
            args.required_model_projection_schema,
            args.require_complete_roots,
        )
        for episode in schedule["episodes"]
    ]
    payload = {
        "schema_version": "1.0.0",
        "audit_type": "posthoc-model-projection-integrity",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "study_id": schedule["study_id"],
        "claim_scope": "measurement integrity only; no effectiveness inference",
        "required_model_projection_schema": (
            args.required_model_projection_schema
        ),
        "require_complete_roots": args.require_complete_roots,
        "audit_script_sha256": sha256_file(Path(__file__).resolve()),
        "schedule": str(schedule_path),
        "schedule_sha256": sha256_file(schedule_path),
        "aggregate": aggregate(episodes),
        "episodes": episodes,
    }
    write_json(args.output.resolve(), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
