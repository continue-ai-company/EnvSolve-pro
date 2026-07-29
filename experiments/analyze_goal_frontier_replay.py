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

from envsolve.constraints import (
    build_goal_obligation_frontier,
    build_model_goal_obligation_frontier,
)
from envsolve.state import EventStore
from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.utils.provenance import sha256_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replay consumed EnvSolve trajectories through the goal-obligation "
            "frontier without executing candidates or querying a model."
        )
    )
    parser.add_argument("--runs-root", type=Path, action="append", required=True)
    parser.add_argument("--study-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-projection-chars", type=int, default=12_000)
    return parser.parse_args()


def _analyze_case(
    case_root: Path,
    *,
    model_projection_chars: int,
) -> list[dict[str, Any]]:
    manifest = read_json(case_root / "manifest.json")
    case = manifest.get("case")
    if not isinstance(case, dict) or not isinstance(case.get("case_id"), str):
        return []
    trajectory = case_root / "generation" / "episode.jsonl"
    state = EventStore(trajectory, case["case_id"]).reconstruct()
    verifications = list(state.verifications)
    results: list[dict[str, Any]] = []
    for verification_index in range(len(verifications)):
        state.verifications = verifications[: verification_index + 1]
        frontier = build_goal_obligation_frontier(state)
        summary = frontier["summary"]
        active = int(summary["active_finding_count"])
        groups = int(summary["obligation_group_count"])
        if active == 0:
            continue
        projected = build_model_goal_obligation_frontier(
            state,
            max_chars=model_projection_chars,
        )
        projected_chars = len(
            json.dumps(projected, ensure_ascii=True, sort_keys=True)
        )
        grouped_surface_count = sum(
            int(item["surface_finding_count"])
            for item in frontier["obligation_groups"]
        )
        if grouped_surface_count != active:
            raise ValueError(
                f"{case['case_id']}: grouped surface count does not preserve findings"
            )
        results.append(
            {
                "case_id": case["case_id"],
                "repository": case.get("repository"),
                "revision": case.get("revision"),
                "run_id": manifest.get("run_id"),
                "method": manifest.get("method"),
                "artifact_root": str(case_root.resolve()),
                "trajectory_sha256": sha256_file(trajectory),
                "verification_index": verification_index,
                "source_verification_id": frontier[
                    "source_verification_id"
                ],
                "finding_set_complete": frontier["finding_set_complete"],
                "active_finding_count": active,
                "obligation_group_count": groups,
                "compression_ratio": summary["compression_ratio"],
                "model_projection_chars": projected_chars,
                "model_projection_complete": projected["summary"][
                    "projection_complete"
                ],
                "source_roles": dict(
                    sorted(
                        sum(
                            (
                                Counter(item["source_roles"])
                                for item in frontier["obligation_groups"]
                            ),
                            Counter(),
                        ).items()
                    )
                ),
                "source_snapshot_sha256": sha256_file(
                    case_root / "generation" / "episode_snapshot.json"
                )
                if (
                    case_root / "generation" / "episode_snapshot.json"
                ).is_file()
                else None,
            }
        )
    state.verifications = verifications
    return results


def _aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    ratios = [
        float(item["compression_ratio"])
        for item in cases
        if item["compression_ratio"] is not None
    ]
    case_maxima: dict[str, dict[str, Any]] = {}
    for item in cases:
        previous = case_maxima.get(item["case_id"])
        rank = (
            int(item["active_finding_count"]),
            int(item["obligation_group_count"]),
        )
        previous_rank = (
            (
                int(previous["active_finding_count"]),
                int(previous["obligation_group_count"]),
            )
            if previous is not None
            else (-1, -1)
        )
        if rank > previous_rank:
            case_maxima[item["case_id"]] = item
    maxima = list(case_maxima.values())
    total_findings = sum(int(item["active_finding_count"]) for item in maxima)
    total_groups = sum(int(item["obligation_group_count"]) for item in maxima)
    return {
        "eligible_trajectory_count": len(cases),
        "distinct_case_count": len(case_maxima),
        "complete_finding_set_trajectory_count": sum(
            item["finding_set_complete"] is True for item in cases
        ),
        "lossless_surface_count_trajectory_count": len(cases),
        "model_projection_complete_trajectory_count": sum(
            item["model_projection_complete"] is True for item in cases
        ),
        "maximum_model_projection_chars": max(
            (int(item["model_projection_chars"]) for item in cases),
            default=0,
        ),
        "trajectory_median_compression_ratio": (
            statistics.median(ratios) if ratios else None
        ),
        "trajectory_maximum_compression_ratio": max(ratios, default=None),
        "case_maximum_weighted_compression_ratio": (
            total_findings / total_groups if total_groups else None
        ),
        "case_maxima": [
            {
                key: item[key]
                for key in (
                    "case_id",
                    "active_finding_count",
                    "obligation_group_count",
                    "compression_ratio",
                    "source_roles",
                )
            }
            for item in sorted(
                maxima,
                key=lambda value: (
                    -int(value["active_finding_count"]),
                    str(value["case_id"]),
                ),
            )
        ],
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
        for result in _analyze_case(
                case_root,
                model_projection_chars=args.model_projection_chars,
            )
    ]
    payload = {
        "schema_version": "1.0.0",
        "study_id": args.study_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim_scope": (
            "Consumed-trajectory representation audit only; no held-out "
            "performance claim."
        ),
        "runs_roots": [str(path.resolve()) for path in args.runs_root],
        "model_projection_chars": args.model_projection_chars,
        "aggregate": _aggregate(cases),
        "trajectories": sorted(
            cases,
            key=lambda item: (
                str(item["case_id"]),
                str(item["run_id"]),
                int(item["verification_index"]),
                str(item["artifact_root"]),
            ),
        ),
    }
    write_json(args.output.resolve(), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
