#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
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
from envsolve.constraints.bootstrap_frontier import (
    build_bootstrap_contradiction_frontier,
)
from envsolve.state import EventStore
from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.utils.provenance import sha256_file


_PROVIDER_FAILURE = re.compile(
    r"(?:APIConnectionError|APITimeoutError|"
    r"EpisodeProviderAcquisitionFailed|Request timed out)",
)
_MUTATION_WITH_SUPPRESSION = re.compile(
    r"\b(?:apt-get|apt|pip|pip3|conda|mamba|micromamba)\b.*"
    r"(?:/dev/null|&>/dev/null)",
    re.IGNORECASE,
)
_GLOBAL_PROVIDER_PATH = re.compile(
    r"(?:export\s+)?PYTHONPATH=.*(?:dist-packages|site-packages)",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize the preregistered bootstrap-frontier-v2 pilot and "
            "preserve algorithm failures as primary outcomes."
        )
    )
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


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


def _goal_counts(state) -> list[int]:
    original = list(state.verifications)
    counts: list[int] = []
    for index in range(len(original)):
        state.verifications = original[: index + 1]
        counts.append(
            int(
                build_goal_obligation_frontier(state)["summary"][
                    "active_finding_count"
                ]
            )
        )
    state.verifications = original
    return counts


def _first_goal_observation_candidate(state) -> str | None:
    for verification in state.verifications:
        details = verification.get("details")
        if not isinstance(details, dict):
            continue
        if (
            details.get("bootstrap_exit_code") == 0
            and isinstance(details.get("summary"), str)
            and details["summary"].startswith("structured verifier:")
        ):
            candidate_id = details.get("candidate_id")
            return candidate_id if isinstance(candidate_id, str) else None
    return None


def _candidate_number(candidate_id: str | None) -> int | None:
    if candidate_id is None:
        return None
    match = re.search(r"([0-9]+)$", candidate_id)
    return int(match.group(1)) if match else None


def _mechanism_metrics(state) -> dict[str, Any]:
    frontier = build_bootstrap_contradiction_frontier(state)
    suppressed: list[dict[str, Any]] = []
    global_paths: list[str] = []
    for action in state.actions.values():
        candidate_id = action.get("action_id")
        command = action.get("command")
        if not isinstance(command, str):
            continue
        hidden_lines = [
            line.strip()
            for line in command.splitlines()
            if _MUTATION_WITH_SUPPRESSION.search(line)
        ]
        if hidden_lines:
            suppressed.append(
                {
                    "candidate_id": candidate_id,
                    "line_count": len(hidden_lines),
                }
            )
        if _GLOBAL_PROVIDER_PATH.search(command):
            global_paths.append(str(candidate_id))

    protected = [
        str(verification.get("details", {}).get("candidate_id"))
        for verification in state.verifications
        if verification.get("details", {}).get("summary")
        == "Candidate modified a goal-protected environment surface"
    ]
    unknown = [
        {
            "candidate_id": verification.get("details", {}).get(
                "candidate_id"
            ),
            "summary": verification.get("details", {}).get("summary"),
        }
        for verification in state.verifications
        if verification.get("passed") is None
    ]

    unclassified: dict[str, set[str]] = defaultdict(set)
    for attempt in frontier["attempts"]:
        failure = attempt.get("failure")
        if (
            isinstance(failure, dict)
            and failure.get("failure_class")
            == "unclassified-bootstrap-failure"
        ):
            unclassified[str(failure["signature"])].add(
                str(attempt["raw_execution_evidence_sha256"])
            )
    unsound_collisions = [
        {
            "failure_signature": signature,
            "distinct_raw_evidence_count": len(hashes),
        }
        for signature, hashes in sorted(unclassified.items())
        if len(hashes) > 1
    ]
    first_goal = _first_goal_observation_candidate(state)
    return {
        "candidate_count": len(state.actions),
        "first_goal_observation_candidate_id": first_goal,
        "candidates_before_first_goal_observation": (
            _candidate_number(first_goal) - 1
            if _candidate_number(first_goal) is not None
            else None
        ),
        "goal_finding_counts": _goal_counts(state),
        "bootstrap_frontier_summary": frontier["summary"],
        "suppressed_mutation_output_candidate_count": len(suppressed),
        "suppressed_mutation_output_candidates": suppressed,
        "global_provider_path_candidate_ids": global_paths,
        "protected_environment_violation_candidate_ids": protected,
        "unknown_verifications": unknown,
        "unsound_unclassified_signature_collision_count": len(
            unsound_collisions
        ),
        "unsound_unclassified_signature_collisions": unsound_collisions,
    }


def _episode(
    episode: dict[str, Any],
    *,
    runs_root: Path,
) -> dict[str, Any]:
    run_id = str(episode["run_id"])
    case_root = _case_root(runs_root, run_id)
    generation = read_json(case_root / "generation" / "result.json")
    ledger = read_json(case_root / "generation" / "budget_ledger.json")
    evaluation_path = case_root / "evaluation" / "result.json"
    evaluation = read_json(evaluation_path) if evaluation_path.is_file() else None
    error = generation.get("error")
    provider_censored = (
        isinstance(error, str) and _PROVIDER_FAILURE.search(error) is not None
    )
    generation_completed = generation.get("generation_completed") is True
    evaluation_completed = (
        isinstance(evaluation, dict)
        and evaluation.get("evaluation_completed") is True
    )
    official_pass = (
        evaluation.get("official_pass")
        if evaluation_completed
        else None
        if provider_censored
        else False
    )
    manifest = read_json(case_root / "manifest.json")
    case = manifest["case"]
    state = EventStore(
        case_root / "generation" / "episode.jsonl",
        str(case["case_id"]),
    ).reconstruct()
    usage = ledger.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    return {
        **episode,
        "artifact_root": str(case_root.resolve()),
        "provider_censored": provider_censored,
        "primary_metric_eligible": not provider_censored,
        "generation_completed": generation_completed,
        "evaluation_completed": evaluation_completed,
        "official_pass": official_pass,
        "generation_error": error,
        "usage": {
            key: usage.get(key)
            for key in (
                "candidates",
                "commands",
                "environments",
                "requests_started",
                "input_tokens",
                "cache_read_tokens",
                "output_tokens",
                "total_tokens",
                "elapsed_wall_clock_seconds",
            )
        },
        "mechanism": _mechanism_metrics(state),
        "artifact_sha256": _artifact_hashes(case_root),
    }


def _pairs(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode in episodes:
        grouped[str(episode["case_id"])].append(episode)
    rows: list[dict[str, Any]] = []
    for case_id, values in sorted(grouped.items()):
        conditions = {
            str(item["condition"]): item
            for item in values
        }
        treatment = conditions["bootstrap-frontier-v2"]
        control = conditions["goal-frontier-v1-control"]
        eligible = all(item["primary_metric_eligible"] for item in values)
        rows.append(
            {
                "case_id": case_id,
                "paired_primary_eligible": eligible,
                "official_pass_treatment": treatment["official_pass"],
                "official_pass_control": control["official_pass"],
                "official_pass_difference": (
                    int(treatment["official_pass"])
                    - int(control["official_pass"])
                    if eligible
                    else None
                ),
                "treatment_minus_control": {
                    key: treatment["usage"][key] - control["usage"][key]
                    for key in (
                        "candidates",
                        "total_tokens",
                        "elapsed_wall_clock_seconds",
                    )
                },
            }
        )
    return rows


def main() -> int:
    args = parse_args()
    preregistration = read_json(args.preregistration.resolve())
    episodes = [
        _episode(
            dict(episode),
            runs_root=args.runs_root.resolve(),
        )
        for episode in preregistration["episodes"]
    ]
    pairs = _pairs(episodes)
    eligible = [item for item in episodes if item["primary_metric_eligible"]]
    payload = {
        "schema_version": "1.0.0",
        "study_id": preregistration["study_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim_scope": preregistration["claim_scope"],
        "analysis_policy": {
            "generation_failure_is_official_pass_failure": True,
            "provider_censoring_is_not_official_pass_failure": True,
            "official_evaluator_feedback_used_online": False,
            "posthoc_case_replacement": False,
        },
        "source_artifacts": {
            "preregistration": str(args.preregistration),
            "preregistration_sha256": sha256_file(args.preregistration),
            "runs_root": str(args.runs_root.resolve()),
        },
        "primary_summary": {
            "selected_pair_count": len(pairs),
            "primary_eligible_pair_count": sum(
                item["paired_primary_eligible"] for item in pairs
            ),
            "official_pass_treatment": sum(
                item["condition"] == "bootstrap-frontier-v2"
                and item["official_pass"] is True
                for item in eligible
            ),
            "official_pass_control": sum(
                item["condition"] == "goal-frontier-v1-control"
                and item["official_pass"] is True
                for item in eligible
            ),
            "official_pass_difference_sum": sum(
                int(item["official_pass_difference"])
                for item in pairs
                if item["official_pass_difference"] is not None
            ),
            "interpretation": (
                "Bootstrap-frontier-v2 underperformed its frozen "
                "goal-frontier-v1 predecessor on this two-case development "
                "pilot (1/2 versus 2/2)."
            ),
        },
        "pairs": pairs,
        "episodes": episodes,
    }
    write_json(args.output.resolve(), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
