#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
from typing import Any


# ruff: noqa: E402 - workspace path bootstrapping precedes local imports.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.constraints import build_goal_obligation_frontier
from envsolve.state import EventStore
from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.utils.provenance import sha256_file


_PIP_INSTALL = re.compile(
    r"(?:^|[;&|]\s*|\n)\s*"
    r"(?:python(?:3(?:\.\d+)?)?\s+-m\s+)?pip(?:3)?\s+install\s+"
    r"(?P<arguments>[^\n;&|]+)",
    re.IGNORECASE,
)
_PIP_OPTIONS_WITH_VALUE = {
    "--constraint",
    "--extra-index-url",
    "--find-links",
    "--index-url",
    "--platform",
    "--python-version",
    "-c",
    "-f",
    "-i",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize the preregistered goal-frontier-v1 pilot while "
            "separating primary-eligible and provider-censored episodes."
        )
    )
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--amendment", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _resolved_run_ids(
    preregistration: dict[str, Any],
    amendment: dict[str, Any],
) -> dict[int, str]:
    resolved = {
        int(item["position"]): str(item["run_id"])
        for item in preregistration["episodes"]
    }
    replacements = {
        1: amendment.get("provider_retry"),
        3: amendment.get("position_3_provider_retry_2"),
    }
    for position, value in replacements.items():
        if isinstance(value, dict) and isinstance(value.get("run_id"), str):
            resolved[position] = value["run_id"]
    return resolved


def _case_root(runs_root: Path, run_id: str) -> Path:
    roots = sorted(
        path.parent
        for path in (runs_root / run_id).glob("*/manifest.json")
    )
    if len(roots) != 1:
        raise ValueError(
            f"{run_id}: expected exactly one case root, found {len(roots)}"
        )
    return roots[0]


def _lexical_install_targets(script: str) -> list[str]:
    targets: set[str] = set()
    for match in _PIP_INSTALL.finditer(script):
        tokens = match.group("arguments").split()
        skip_next = False
        for token in tokens:
            if skip_next:
                skip_next = False
                continue
            if token in _PIP_OPTIONS_WITH_VALUE:
                skip_next = True
                continue
            if token.startswith("-"):
                continue
            if token in {".", "./", "-e"} or token.startswith("./"):
                continue
            targets.add(token.strip("'\""))
    return sorted(targets)


def _goal_trajectory_metrics(
    case_root: Path,
    case_id: str,
) -> dict[str, Any]:
    trajectory = case_root / "generation" / "episode.jsonl"
    state = EventStore(trajectory, case_id).reconstruct()
    verifications = list(state.verifications)
    finding_counts: list[int] = []
    group_counts: list[int] = []
    for index in range(len(verifications)):
        state.verifications = verifications[: index + 1]
        frontier = build_goal_obligation_frontier(state)
        finding_counts.append(
            int(frontier["summary"]["active_finding_count"])
        )
        group_counts.append(
            int(frontier["summary"]["obligation_group_count"])
        )
    state.verifications = verifications

    projection_completeness: list[bool] = []
    install_targets: set[str] = set()
    for action in state.actions.values():
        command = action.get("command")
        if isinstance(command, str):
            install_targets.update(_lexical_install_targets(command))
        metadata = action.get("metadata")
        snapshot = (
            metadata.get("goal_obligation_frontier_snapshot")
            if isinstance(metadata, dict)
            else None
        )
        summary = snapshot.get("summary") if isinstance(snapshot, dict) else None
        if isinstance(summary, dict) and isinstance(
            summary.get("projection_complete"), bool
        ):
            projection_completeness.append(summary["projection_complete"])

    first_positive_index = next(
        (
            index
            for index, value in enumerate(finding_counts)
            if value > 0
        ),
        None,
    )
    return {
        "candidate_execution_count": len(state.actions),
        "goal_finding_counts": finding_counts,
        "goal_obligation_group_counts": group_counts,
        "maximum_active_finding_count": max(finding_counts, default=0),
        "maximum_obligation_group_count": max(group_counts, default=0),
        "post_first_positive_finding_delta": (
            finding_counts[-1] - finding_counts[first_positive_index]
            if first_positive_index is not None
            else None
        ),
        "lexical_install_target_count": len(install_targets),
        "lexical_install_targets": sorted(install_targets),
        "frontier_projection_count": len(projection_completeness),
        "frontier_projection_complete_count": sum(projection_completeness),
    }


def _artifact_hashes(case_root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for relative in (
        "generation/result.json",
        "generation/episode.jsonl",
        "generation/episode_snapshot.json",
        "generation/budget_ledger.json",
        "evaluation/result.json",
    ):
        path = case_root / relative
        if path.is_file():
            values[relative] = sha256_file(path)
    return values


def _analyze_episode(
    episode: dict[str, Any],
    *,
    run_id: str,
    runs_root: Path,
    censored_run_ids: set[str],
) -> dict[str, Any]:
    case_root = _case_root(runs_root, run_id)
    generation = read_json(case_root / "generation" / "result.json")
    ledger = read_json(case_root / "generation" / "budget_ledger.json")
    evaluation_path = case_root / "evaluation" / "result.json"
    evaluation = read_json(evaluation_path) if evaluation_path.is_file() else None
    generation_completed = generation.get("generation_completed") is True
    evaluation_completed = (
        isinstance(evaluation, dict)
        and evaluation.get("evaluation_completed") is True
    )
    provider_censored = run_id in censored_run_ids
    primary_eligible = (
        generation_completed and evaluation_completed and not provider_censored
    )
    usage = ledger.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    raw_metrics = (
        evaluation.get("raw_metrics")
        if isinstance(evaluation, dict)
        else None
    )
    return {
        **episode,
        "selected_run_id": run_id,
        "artifact_root": str(case_root.resolve()),
        "provider_censored": provider_censored,
        "primary_metric_eligible": primary_eligible,
        "generation_completed": generation_completed,
        "evaluation_completed": evaluation_completed,
        "official_pass": (
            evaluation.get("official_pass")
            if isinstance(evaluation, dict)
            else None
        ),
        "generation_error": generation.get("error"),
        "usage": {
            key: usage.get(key)
            for key in (
                "candidates",
                "commands",
                "environments",
                "requests_started",
                "provider_retries",
                "input_tokens",
                "cache_read_tokens",
                "output_tokens",
                "total_tokens",
                "elapsed_wall_clock_seconds",
            )
        },
        "official_raw_metrics": raw_metrics,
        "mechanism": _goal_trajectory_metrics(
            case_root,
            str(episode["case_id"]),
        ),
        "artifact_sha256": _artifact_hashes(case_root),
    }


def _paired_results(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_case: dict[str, list[dict[str, Any]]] = {}
    for episode in episodes:
        by_case.setdefault(str(episode["case_id"]), []).append(episode)
    pairs: list[dict[str, Any]] = []
    for case_id, values in sorted(by_case.items()):
        eligible = all(item["primary_metric_eligible"] for item in values)
        conditions = {
            str(item["condition"]): item
            for item in values
        }
        treatment = conditions.get("goal-frontier-v1")
        control = conditions.get("frozen-fresh-control")
        pair: dict[str, Any] = {
            "case_id": case_id,
            "paired_primary_eligible": eligible,
            "disposition": (
                "primary-comparison"
                if eligible
                else "mechanism-only-provider-censored"
            ),
            "conditions": {
                condition: {
                    "selected_run_id": item["selected_run_id"],
                    "official_pass": item["official_pass"],
                    "primary_metric_eligible": item["primary_metric_eligible"],
                }
                for condition, item in sorted(conditions.items())
            },
        }
        if eligible and treatment is not None and control is not None:
            treatment_usage = treatment["usage"]
            control_usage = control["usage"]
            pair["official_pass_difference"] = (
                int(treatment["official_pass"])
                - int(control["official_pass"])
            )
            pair["treatment_minus_control"] = {
                "candidates": (
                    treatment_usage["candidates"]
                    - control_usage["candidates"]
                ),
                "total_tokens": (
                    treatment_usage["total_tokens"]
                    - control_usage["total_tokens"]
                ),
                "elapsed_wall_clock_seconds": (
                    treatment_usage["elapsed_wall_clock_seconds"]
                    - control_usage["elapsed_wall_clock_seconds"]
                ),
            }
            pair["treatment_over_control"] = {
                "total_tokens": (
                    treatment_usage["total_tokens"]
                    / control_usage["total_tokens"]
                ),
                "elapsed_wall_clock_seconds": (
                    treatment_usage["elapsed_wall_clock_seconds"]
                    / control_usage["elapsed_wall_clock_seconds"]
                ),
            }
        pairs.append(pair)
    return pairs


def main() -> int:
    args = parse_args()
    preregistration = read_json(args.preregistration.resolve())
    amendment = read_json(args.amendment.resolve())
    resolved = _resolved_run_ids(preregistration, amendment)
    censored_run_ids = {
        str(item["run_id"])
        for item in amendment.get("provider_censored_failures", [])
        if isinstance(item, dict) and isinstance(item.get("run_id"), str)
    }
    episodes = [
        _analyze_episode(
            dict(episode),
            run_id=resolved[int(episode["position"])],
            runs_root=args.runs_root.resolve(),
            censored_run_ids=censored_run_ids,
        )
        for episode in preregistration["episodes"]
    ]
    pairs = _paired_results(episodes)
    eligible_pairs = [
        pair for pair in pairs if pair["paired_primary_eligible"]
    ]
    payload = {
        "schema_version": "1.0.0",
        "study_id": preregistration["study_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim_scope": preregistration["claim_scope"],
        "analysis_policy": {
            "provider_censored_runs_excluded_from_primary_metric": True,
            "censored_selected_cases_not_replaced": True,
            "tokens_and_wall_clock_reported_as_outcomes": True,
            "lexical_install_targets_are_descriptive_not_package_ground_truth": True,
        },
        "source_artifacts": {
            "preregistration": str(args.preregistration),
            "preregistration_sha256": sha256_file(args.preregistration),
            "amendment": str(args.amendment),
            "amendment_sha256": sha256_file(args.amendment),
            "runs_root": str(args.runs_root.resolve()),
        },
        "primary_summary": {
            "selected_pair_count": len(pairs),
            "primary_eligible_pair_count": len(eligible_pairs),
            "official_pass_treatment": sum(
                pair["conditions"]["goal-frontier-v1"]["official_pass"] is True
                for pair in eligible_pairs
            ),
            "official_pass_control": sum(
                pair["conditions"]["frozen-fresh-control"]["official_pass"] is True
                for pair in eligible_pairs
            ),
            "official_pass_difference_sum": sum(
                int(pair["official_pass_difference"])
                for pair in eligible_pairs
            ),
            "interpretation": (
                "The only primary-eligible pair is a pass/pass tie. The "
                "second selected pair is provider-censored and supports no "
                "Official Pass claim."
            ),
        },
        "pairs": pairs,
        "episodes": episodes,
    }
    write_json(args.output.resolve(), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
