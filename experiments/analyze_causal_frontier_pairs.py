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

from envsolve.constraints import build_causal_constraint_frontier
from envsolve.state import EventStore
from envsolve.state.events import EventType, StateEvent
from envsolve.state.reducer import reduce_events
from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.utils.provenance import sha256_file


TARGETS = {
    "langchain-ai/langgraph": {
        "root_kind": "runtime_compatibility_frontier",
        "provider": "pyo3",
        "subject": "python",
    },
    "nonebot/nonebot2": {
        "root_kind": "runtime_compatibility_frontier",
        "provider": "pyo3",
        "subject": "python",
    },
    "conan-io/conan-package-tools": {
        "root_kind": "runtime_missing_dependency",
        "subject": "six.moves",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze the frozen P5 flat/causal consumed-case pairs."
    )
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _matches(root: dict[str, Any], target: dict[str, str]) -> bool:
    return all(root.get(key) == value for key, value in target.items())


def _frontier_timeline(
    trajectory: Path,
    case_id: str,
    target: dict[str, str],
) -> list[dict[str, Any]]:
    events = EventStore(trajectory, case_id).read()
    prefix: list[StateEvent] = []
    timeline: list[dict[str, Any]] = []
    completed_candidates = 0
    for event in events:
        if event.event_type == EventType.ACTION_PROPOSED.value:
            metadata = event.payload.get("metadata")
            metadata = metadata if isinstance(metadata, dict) else {}
            persisted = metadata.get("constraint_frontier_snapshot")
            expected_hash = metadata.get("constraint_frontier_sha256")
            if isinstance(persisted, dict):
                frontier = persisted
                encoded = json.dumps(
                    persisted,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                observed_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
                frontier_source = "persisted-model-projection"
                frontier_hash_valid = observed_hash == expected_hash
            else:
                frontier = build_causal_constraint_frontier(
                    reduce_events(case_id, prefix)
                )
                frontier_source = "offline-derived"
                frontier_hash_valid = None
            roots = frontier["causal_roots"]
            timeline.append(
                {
                    "phase": "decision",
                    "candidate_id": event.payload["action_id"],
                    "after_candidate_index": completed_candidates,
                    "target_present": any(_matches(root, target) for root in roots),
                    "target_roots": [
                        root for root in roots if _matches(root, target)
                    ],
                    "frontier_source": frontier_source,
                    "frontier_hash_valid": frontier_hash_valid,
                    "frontier_summary": frontier["summary"],
                }
            )
        prefix.append(event)
        if event.event_type == EventType.ACTION_FINISHED.value:
            completed_candidates += 1
    final_frontier = build_causal_constraint_frontier(
        reduce_events(case_id, events)
    )
    final_roots = final_frontier["causal_roots"]
    timeline.append(
        {
            "phase": "terminal",
            "candidate_id": None,
            "after_candidate_index": completed_candidates,
            "target_present": any(_matches(root, target) for root in final_roots),
            "target_roots": [
                root for root in final_roots if _matches(root, target)
            ],
            "frontier_source": "offline-derived-terminal-state",
            "frontier_hash_valid": None,
            "frontier_summary": final_frontier["summary"],
        }
    )
    return timeline


def target_metrics(timeline: list[dict[str, Any]]) -> dict[str, Any]:
    observed = [item for item in timeline if item["target_present"]]
    decision_observations = [
        item for item in observed if item["phase"] == "decision"
    ]
    first = observed[0] if observed else None
    closed_at = None
    if first is not None:
        closed_at = next(
            (
                item
                for item in timeline
                if item["after_candidate_index"]
                > first["after_candidate_index"]
                and not item["target_present"]
            ),
            None,
        )
    return {
        "target_observed": first is not None,
        "target_first_observed_after_candidate": (
            first["after_candidate_index"] if first is not None else None
        ),
        "target_recurrence_decisions": len(decision_observations),
        "target_closed": closed_at is not None,
        "target_closed_by_candidate": (
            closed_at["after_candidate_index"] if closed_at is not None else None
        ),
    }


def _read_optional(path: Path) -> dict[str, Any]:
    return read_json(path) if path.is_file() else {}


def analyze_episode(
    episode: dict[str, Any],
    runs_root: Path,
) -> dict[str, Any]:
    case_id = str(episode["case_id"])
    case_root = (
        runs_root / safe_name(str(episode["run_id"])) / safe_name(case_id)
    )
    manifest = read_json(case_root / "manifest.json")
    repository = str(manifest["case"]["repository"])
    target = TARGETS[repository]
    trajectory = case_root / "generation" / "episode.jsonl"
    timeline = _frontier_timeline(trajectory, case_id, target)
    generation = _read_optional(case_root / "generation" / "result.json")
    evaluation = _read_optional(case_root / "evaluation" / "result.json")
    ledger = _read_optional(case_root / "generation" / "budget_ledger.json")
    generation_metadata = generation.get("metadata") or {}
    candidate_output = generation_metadata.get("candidate_output") or {}
    usage = ledger.get("usage") or {}
    exhausted = ledger.get("exhausted_limits") or []
    evaluation_metadata = evaluation.get("metadata") or {}
    official_pass = evaluation.get("official_pass")
    integrity_ok = (
        evaluation.get("evaluation_completed") is True
        and isinstance(official_pass, bool)
        and evaluation_metadata.get("identity_matches") is True
    )
    frontier_trace_integrity_ok = (
        all(
            item["frontier_source"] == "persisted-model-projection"
            and item["frontier_hash_valid"] is True
            for item in timeline
            if item["phase"] == "decision"
        )
        if episode["condition"] == "causal-frontier"
        else True
    )
    return {
        "position": episode["position"],
        "pair": episode["pair"],
        "condition": episode["condition"],
        "method": episode["method"],
        "case_id": case_id,
        "repository": repository,
        "artifact_root": str(case_root.resolve()),
        "trajectory_sha256": sha256_file(trajectory),
        "target": target,
        "target_metrics": target_metrics(timeline),
        "frontier_timeline": timeline,
        "official_pass": official_pass,
        "internal_certification": candidate_output.get("certification"),
        "measurement_integrity_ok": (
            integrity_ok and frontier_trace_integrity_ok
        ),
        "official_evaluation_integrity_ok": integrity_ok,
        "frontier_trace_integrity_ok": frontier_trace_integrity_ok,
        "candidates": usage.get("candidates"),
        "candidate_cap_bound": any(
            "candidate" in str(item).lower() for item in exhausted
        ),
        "usage": {
            key: usage.get(key)
            for key in (
                "input_tokens",
                "output_tokens",
                "cache_read_tokens",
                "total_tokens",
                "estimated_cost_usd",
                "elapsed_wall_clock_seconds",
            )
        },
        "termination": ledger.get("termination"),
        "generation_error": generation.get("error"),
    }


def aggregate(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    pairs: list[dict[str, Any]] = []
    for pair_id in sorted({int(item["pair"]) for item in episodes}):
        values = [item for item in episodes if int(item["pair"]) == pair_id]
        flat = next(item for item in values if item["condition"] == "flat")
        causal = next(
            item for item in values if item["condition"] == "causal-frontier"
        )
        success_delta = int(causal["official_pass"] is True) - int(
            flat["official_pass"] is True
        )
        closure_delta = int(causal["target_metrics"]["target_closed"]) - int(
            flat["target_metrics"]["target_closed"]
        )
        pairs.append(
            {
                "pair": pair_id,
                "repository": flat["repository"],
                "official_success_delta_causal_minus_flat": success_delta,
                "target_closure_delta_causal_minus_flat": closure_delta,
                "flat": {
                    "official_pass": flat["official_pass"],
                    **flat["target_metrics"],
                },
                "causal_frontier": {
                    "official_pass": causal["official_pass"],
                    **causal["target_metrics"],
                },
            }
        )
    integrity_ok = all(item["measurement_integrity_ok"] for item in episodes)
    improves_mechanism = any(
        item["official_success_delta_causal_minus_flat"] > 0
        or item["target_closure_delta_causal_minus_flat"] > 0
        for item in pairs
    )
    no_success_regression = all(
        item["official_success_delta_causal_minus_flat"] >= 0 for item in pairs
    )
    return {
        "episode_count": len(episodes),
        "pair_count": len(pairs),
        "official_passes": {
            condition: sum(
                item["official_pass"] is True
                for item in episodes
                if item["condition"] == condition
            )
            for condition in ("flat", "causal-frontier")
        },
        "target_closures": {
            condition: sum(
                item["target_metrics"]["target_closed"]
                for item in episodes
                if item["condition"] == condition
            )
            for condition in ("flat", "causal-frontier")
        },
        "measurement_integrity_ok": integrity_ok,
        "mechanism_improvement_observed": improves_mechanism,
        "no_paired_official_success_regression": no_success_regression,
        "preregistered_proceed_rule_satisfied": (
            integrity_ok and improves_mechanism and no_success_regression
        ),
        "pairs": pairs,
    }


def main() -> int:
    args = parse_args()
    schedule_path = args.schedule.resolve()
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    episodes = [
        analyze_episode(episode, args.runs_root.resolve())
        for episode in schedule["episodes"]
    ]
    payload = {
        "schema_version": "1.0.0",
        "study_id": schedule["study_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim_scope": schedule["claim_scope"],
        "schedule": str(schedule_path),
        "schedule_sha256": sha256_file(schedule_path),
        "aggregate": aggregate(episodes),
        "episodes": episodes,
    }
    write_json(args.output.resolve(), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
