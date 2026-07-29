#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
from typing import Any


# ruff: noqa: E402 - workspace path bootstrapping precedes local imports.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.constraints.bootstrap_frontier import (
    build_bootstrap_contradiction_frontier,
    build_model_bootstrap_contradiction_frontier,
)
from envsolve.state import EventStore
from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.utils.provenance import sha256_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replay consumed goal-contract trajectories through the bootstrap "
            "contradiction frontier without executing candidates or querying "
            "a model."
        )
    )
    parser.add_argument("--runs-root", type=Path, action="append", required=True)
    parser.add_argument("--study-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-projection-chars", type=int, default=10_000)
    return parser.parse_args()


def _candidate_id(verification: dict[str, Any]) -> str | None:
    details = verification.get("details")
    value = details.get("candidate_id") if isinstance(details, dict) else None
    return value if isinstance(value, str) else None


def _analyze_case(
    case_root: Path,
    *,
    model_projection_chars: int,
) -> dict[str, Any] | None:
    manifest = read_json(case_root / "manifest.json")
    case = manifest.get("case")
    if not isinstance(case, dict) or not isinstance(case.get("case_id"), str):
        return None
    trajectory = case_root / "generation" / "episode.jsonl"
    if not trajectory.is_file():
        return None
    state = EventStore(trajectory, case["case_id"]).reconstruct()
    original_actions = state.actions
    original_verifications = list(state.verifications)
    prefix_rows: list[dict[str, Any]] = []
    for index in range(len(original_verifications)):
        state.verifications = original_verifications[: index + 1]
        allowed = {
            candidate_id
            for verification in state.verifications
            if (candidate_id := _candidate_id(verification)) is not None
        }
        state.actions = {
            key: value
            for key, value in original_actions.items()
            if key in allowed
        }
        frontier = build_bootstrap_contradiction_frontier(state)
        projection = build_model_bootstrap_contradiction_frontier(
            state,
            max_chars=model_projection_chars,
        )
        dominated = [
            item["runtime_branch"]
            for item in frontier["runtime_branches"]
            if item["search_status"]
            == "search-dominated-by-observed-failures"
        ]
        prefix_rows.append(
            {
                "verification_prefix_length": index + 1,
                "source_candidate_id": _candidate_id(
                    original_verifications[index]
                ),
                "observed_attempt_count": frontier["summary"][
                    "observed_attempt_count"
                ],
                "failed_bootstrap_count": frontier["summary"][
                    "failed_bootstrap_count"
                ],
                "successful_bootstrap_count": frontier["summary"][
                    "successful_bootstrap_count"
                ],
                "search_dominated_runtime_branches": dominated,
                "repeated_failure_signature_count": frontier["summary"][
                    "repeated_failure_signature_count"
                ],
                "projection_complete": projection["summary"][
                    "projection_complete"
                ],
                "projection_chars": len(
                    json.dumps(
                        projection,
                        ensure_ascii=True,
                        sort_keys=True,
                    )
                ),
            }
        )
    state.actions = original_actions
    state.verifications = original_verifications
    final = build_bootstrap_contradiction_frontier(state)
    attempts = final["attempts"]
    first_dominated = next(
        (
            row
            for row in prefix_rows
            if row["search_dominated_runtime_branches"]
        ),
        None,
    )
    later_successful_branches: set[str] = set()
    if first_dominated is not None:
        dominated = set(first_dominated["search_dominated_runtime_branches"])
        trigger_index = int(first_dominated["verification_prefix_length"])
        later_successful_branches = {
            str(runtime)
            for attempt in attempts[trigger_index:]
            if attempt["outcome"] == "succeeded"
            for runtime in attempt["runtime_branches"]
            if str(runtime) in dominated
        }
    return {
        "case_id": case["case_id"],
        "repository": case.get("repository"),
        "revision": case.get("revision"),
        "run_id": manifest.get("run_id") or case_root.parent.name,
        "method": manifest.get("method"),
        "artifact_root": str(case_root.resolve()),
        "trajectory_sha256": sha256_file(trajectory),
        "observed_attempt_count": final["summary"]["observed_attempt_count"],
        "failed_bootstrap_count": final["summary"]["failed_bootstrap_count"],
        "successful_bootstrap_count": final["summary"][
            "successful_bootstrap_count"
        ],
        "infrastructure_censored_count": final["summary"][
            "infrastructure_censored_count"
        ],
        "classified_failure_count": sum(
            attempt.get("failure", {}).get("failure_class")
            != "unclassified-bootstrap-failure"
            for attempt in attempts
            if attempt["outcome"] == "failed"
        ),
        "failure_classes": dict(
            sorted(
                Counter(
                    str(attempt["failure"]["failure_class"])
                    for attempt in attempts
                    if attempt["outcome"] == "failed"
                ).items()
            )
        ),
        "first_search_dominated_prefix": (
            first_dominated["verification_prefix_length"]
            if first_dominated is not None
            else None
        ),
        "first_search_dominated_candidate_id": (
            first_dominated["source_candidate_id"]
            if first_dominated is not None
            else None
        ),
        "future_same_branch_success_after_search_dominance": sorted(
            later_successful_branches
        ),
        "prefixes": prefix_rows,
    }


def _aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    failed = sum(int(item["failed_bootstrap_count"]) for item in cases)
    classified = sum(int(item["classified_failure_count"]) for item in cases)
    triggers = [
        item
        for item in cases
        if item["first_search_dominated_prefix"] is not None
    ]
    trigger_prefixes = [
        int(item["first_search_dominated_prefix"]) for item in triggers
    ]
    prefix_rows = [
        prefix_row
        for item in cases
        for prefix_row in item["prefixes"]
    ]
    return {
        "trajectory_count": len(cases),
        "trajectory_with_bootstrap_observation_count": sum(
            int(item["observed_attempt_count"]) > 0 for item in cases
        ),
        "failed_bootstrap_count": failed,
        "infrastructure_censored_count": sum(
            int(item["infrastructure_censored_count"])
            for item in cases
        ),
        "classified_failure_count": classified,
        "classified_failure_rate": classified / failed if failed else None,
        "search_dominance_trigger_trajectory_count": len(triggers),
        "median_first_search_dominated_prefix": (
            statistics.median(trigger_prefixes)
            if trigger_prefixes
            else None
        ),
        "future_same_branch_success_after_search_dominance_count": sum(
            bool(item["future_same_branch_success_after_search_dominance"])
            for item in triggers
        ),
        "projection_prefix_count": len(prefix_rows),
        "projection_complete_prefix_count": sum(
            row["projection_complete"] is True for row in prefix_rows
        ),
        "maximum_projection_chars": max(
            (int(row["projection_chars"]) for row in prefix_rows),
            default=0,
        ),
        "failure_classes": dict(
            sorted(
                sum(
                    (
                        Counter(item["failure_classes"])
                        for item in cases
                    ),
                    Counter(),
                ).items()
            )
        ),
    }


def main() -> int:
    args = parse_args()
    roots: dict[str, Path] = {}
    for runs_root in args.runs_root:
        for manifest_path in sorted(runs_root.resolve().rglob("manifest.json")):
            case_root = manifest_path.parent
            trajectory = case_root / "generation" / "episode.jsonl"
            if trajectory.is_file():
                roots[str(case_root.resolve())] = case_root
    cases = [
        result
        for case_root in roots.values()
        if (
            result := _analyze_case(
                case_root,
                model_projection_chars=args.model_projection_chars,
            )
        )
        is not None
    ]
    payload = {
        "schema_version": "1.0.0",
        "study_id": args.study_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim_scope": (
            "Consumed-trajectory representation and trigger audit only; no "
            "held-out performance claim."
        ),
        "inference_semantics": {
            "search_dominance_is_soft": True,
            "future_same_branch_success_is_not_a_logical_false_positive": (
                "It measures why a hard branch exclusion would be unsafe."
            ),
            "official_evaluator_feedback_used": False,
            "model_queries_executed": False,
            "candidate_commands_executed": False,
        },
        "runs_roots": [str(path.resolve()) for path in args.runs_root],
        "model_projection_chars": args.model_projection_chars,
        "aggregate": _aggregate(cases),
        "trajectories": sorted(
            cases,
            key=lambda item: (
                str(item["case_id"]),
                str(item["run_id"]),
                str(item["artifact_root"]),
            ),
        ),
    }
    write_json(args.output.resolve(), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
