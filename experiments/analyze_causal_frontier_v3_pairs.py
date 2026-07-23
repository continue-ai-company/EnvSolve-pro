#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
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
from experiments.analyze_causal_frontier_pairs import TARGETS, _matches, target_metrics
from experiments.audit_causal_frontier_projection import audit_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze measurement-valid P5 V3 flat/causal pairs."
    )
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _read_optional(path: Path) -> dict[str, Any]:
    return read_json(path) if path.is_file() else {}


def _infrastructure_signatures(events: list[StateEvent]) -> list[str]:
    signatures = []
    for event in events:
        if event.event_type != EventType.VERIFICATION_RECORDED.value:
            continue
        details = event.payload.get("details")
        verifier = details.get("verifier_details") if isinstance(details, dict) else None
        error = verifier.get("infrastructure_error") if isinstance(verifier, dict) else None
        signature = (
            verifier.get("infrastructure_signature")
            if isinstance(verifier, dict)
            else None
        )
        if isinstance(error, str) and error:
            signatures.append(
                f"{error}:{signature}" if isinstance(signature, str) else error
            )
    return sorted(set(signatures))


def classify_terminal(
    generation: dict[str, Any],
    evaluation: dict[str, Any],
    ledger: dict[str, Any],
    events: list[StateEvent],
) -> dict[str, Any]:
    infrastructure = _infrastructure_signatures(events)
    if infrastructure:
        return {
            "class": "infrastructure_censored",
            "success": None,
            "source": "internal-verifier",
            "infrastructure_signatures": infrastructure,
        }
    metadata = evaluation.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    official_pass = evaluation.get("official_pass")
    if (
        evaluation.get("evaluation_completed") is True
        and isinstance(official_pass, bool)
        and metadata.get("identity_matches") is True
    ):
        return {
            "class": "official_pass" if official_pass else "official_fail",
            "success": official_pass,
            "source": "identity-matched-official-evaluation",
            "infrastructure_signatures": [],
        }
    exhausted = ledger.get("exhausted_limits")
    exhausted = exhausted if isinstance(exhausted, list) else []
    error = str(generation.get("error") or "").lower()
    if generation.get("generation_completed") is False and (
        "candidates" in exhausted or "candidate budget exhausted" in error
    ):
        return {
            "class": "algorithmic_no_candidate",
            "success": False,
            "source": "candidate-budget-terminal",
            "infrastructure_signatures": [],
        }
    return {
        "class": "terminal_unknown",
        "success": None,
        "source": "insufficient-terminal-evidence",
        "infrastructure_signatures": [],
    }


def _timeline(
    events: list[StateEvent],
    case_id: str,
    condition: str,
    target: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    prefix: list[StateEvent] = []
    timeline: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    completed = 0
    for event in events:
        if event.event_type == EventType.ACTION_PROPOSED.value:
            state = reduce_events(case_id, prefix)
            if condition == "causal-frontier":
                metadata = event.payload.get("metadata")
                audit = audit_snapshot(metadata, "1.0.0", True)
                audits.append(
                    {
                        "candidate_id": event.payload["action_id"],
                        "event_sequence": event.sequence,
                        **audit,
                    }
                )
                value = metadata if isinstance(metadata, dict) else {}
                frontier = value.get("constraint_frontier_snapshot")
                roots = (
                    frontier.get("causal_roots", [])
                    if isinstance(frontier, dict) and audit["integrity_ok"]
                    else []
                )
                source = "persisted-model-projection"
            else:
                frontier = build_causal_constraint_frontier(state)
                roots = frontier["causal_roots"]
                source = "offline-derived-diagnostic"
            timeline.append(
                {
                    "phase": "decision",
                    "candidate_id": event.payload["action_id"],
                    "after_candidate_index": completed,
                    "target_present": any(_matches(root, target) for root in roots),
                    "target_roots": [
                        root for root in roots if _matches(root, target)
                    ],
                    "frontier_source": source,
                }
            )
        prefix.append(event)
        if event.event_type == EventType.ACTION_FINISHED.value:
            completed += 1
    final = build_causal_constraint_frontier(reduce_events(case_id, events))
    final_roots = final["causal_roots"]
    timeline.append(
        {
            "phase": "terminal",
            "candidate_id": None,
            "after_candidate_index": completed,
            "target_present": any(_matches(root, target) for root in final_roots),
            "target_roots": [
                root for root in final_roots if _matches(root, target)
            ],
            "frontier_source": "offline-derived-terminal-state",
        }
    )
    return timeline, audits


def analyze_episode(episode: dict[str, Any], runs_root: Path) -> dict[str, Any]:
    case_id = str(episode["case_id"])
    case_root = runs_root / safe_name(str(episode["run_id"])) / safe_name(case_id)
    manifest = read_json(case_root / "manifest.json")
    repository = str(manifest["case"]["repository"])
    trajectory = case_root / "generation" / "episode.jsonl"
    events = EventStore(trajectory, case_id).read()
    timeline, projection_audits = _timeline(
        events,
        case_id,
        str(episode["condition"]),
        TARGETS[repository],
    )
    generation = _read_optional(case_root / "generation/result.json")
    evaluation = _read_optional(case_root / "evaluation/result.json")
    ledger = _read_optional(case_root / "generation/budget_ledger.json")
    terminal = classify_terminal(generation, evaluation, ledger, events)
    projection_integrity = (
        bool(projection_audits)
        and all(item["integrity_ok"] for item in projection_audits)
        if episode["condition"] == "causal-frontier"
        else True
    )
    return {
        "position": episode["position"],
        "pair": episode["pair"],
        "block": episode.get("block"),
        "condition": episode["condition"],
        "method": episode["method"],
        "seed": episode.get("seed"),
        "case_id": case_id,
        "repository": repository,
        "run_id": episode["run_id"],
        "trajectory_sha256": sha256_file(trajectory),
        "projection_integrity_ok": projection_integrity,
        "projection_audits": projection_audits,
        "target": TARGETS[repository],
        "target_metrics": target_metrics(timeline),
        "frontier_timeline": timeline,
        "terminal": terminal,
        "usage": (ledger.get("usage") or {}),
    }


def aggregate(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = []
    for pair_id in sorted({int(item["pair"]) for item in episodes}):
        values = [item for item in episodes if int(item["pair"]) == pair_id]
        flat = next(item for item in values if item["condition"] == "flat")
        causal = next(item for item in values if item["condition"] == "causal-frontier")
        successes = (flat["terminal"]["success"], causal["terminal"]["success"])
        eligible = (
            all(isinstance(value, bool) for value in successes)
            and causal["projection_integrity_ok"]
        )
        comparable = (
            flat["target_metrics"]["target_observed"]
            and causal["target_metrics"]["target_observed"]
        )
        pairs.append(
            {
                "pair": pair_id,
                "block": flat.get("block"),
                "repository": flat["repository"],
                "eligible": eligible,
                "target_comparable": comparable,
                "official_success_delta_causal_minus_flat": (
                    int(successes[1]) - int(successes[0]) if eligible else None
                ),
                "target_closure_delta_causal_minus_flat": (
                    int(causal["target_metrics"]["target_closed"])
                    - int(flat["target_metrics"]["target_closed"])
                    if eligible and comparable
                    else None
                ),
            }
        )
    eligible = [item for item in pairs if item["eligible"]]
    comparable = [item for item in eligible if item["target_comparable"]]
    return {
        "episode_count": len(episodes),
        "pair_count": len(pairs),
        "eligible_pair_count": len(eligible),
        "censored_pair_count": len(pairs) - len(eligible),
        "causal_projection_integrity_ok": all(
            item["projection_integrity_ok"]
            for item in episodes
            if item["condition"] == "causal-frontier"
        ),
        "official_passes": {
            condition: sum(
                item["terminal"]["success"] is True
                for item in episodes
                if item["condition"] == condition
            )
            for condition in ("flat", "causal-frontier")
        },
        "target_comparable_pair_count": len(comparable),
        "official_success_delta_sum": sum(
            int(item["official_success_delta_causal_minus_flat"])
            for item in eligible
        ),
        "target_closure_delta_sum": sum(
            int(item["target_closure_delta_causal_minus_flat"])
            for item in comparable
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
    write_json(
        args.output.resolve(),
        {
            "schema_version": "1.0.0",
            "study_id": schedule["study_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "claim_scope": schedule["claim_scope"],
            "analysis_script_sha256": sha256_file(Path(__file__).resolve()),
            "schedule": str(schedule_path),
            "schedule_sha256": sha256_file(schedule_path),
            "aggregate": aggregate(episodes),
            "episodes": episodes,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
