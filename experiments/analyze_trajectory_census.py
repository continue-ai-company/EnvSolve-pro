#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import read_jsonl, write_json
from envsolve_harness.storage.artifacts import safe_name


CATEGORIES = (
    "success",
    "evaluator_gap",
    "observability_gap",
    "closure_gap",
    "operation_nonviability",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify EnvSolve trajectories by their dominant blocking layer."
    )
    parser.add_argument("--case-file", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _candidate_index(candidate_id: str) -> int:
    try:
        return int(candidate_id.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return sys.maxsize


def candidate_verifications(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for event in events:
        if event.get("event_type") != "verification_recorded":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        details = payload.get("details")
        if not isinstance(details, dict):
            continue
        candidate_id = details.get("candidate_id")
        if not isinstance(candidate_id, str):
            continue
        verifier_details = details.get("verifier_details")
        if not isinstance(verifier_details, dict):
            verifier_details = {}
        report_details = verifier_details.get("report_details")
        if not isinstance(report_details, dict):
            report_details = {}
        effect_audit = report_details.get("repository_effect_audit")
        if not isinstance(effect_audit, dict):
            effect_audit = {}
        assessment = details.get("candidate_assessment")
        if not isinstance(assessment, dict):
            assessment = {}
        candidates.append(
            {
                "candidate_id": candidate_id,
                "candidate_index": _candidate_index(candidate_id),
                "bootstrap_exit_code": details.get("bootstrap_exit_code"),
                "completed": verifier_details.get("completed") is True,
                "effect_valid": effect_audit.get("valid") is True,
                "reported_passed": details.get("reported_passed") is True,
                "admissible": assessment.get("admissible") is True,
                "satisfied_constraints": int(
                    assessment.get("satisfied_constraints", 0) or 0
                ),
                "unknown_constraints": int(
                    assessment.get("unknown_constraints", 0) or 0
                ),
                "unresolved_constraints": int(
                    assessment.get("unresolved_constraints", 0) or 0
                ),
            }
        )
    return candidates


def best_complete_candidate(
    candidates: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    eligible = [
        candidate
        for candidate in candidates
        if candidate["bootstrap_exit_code"] == 0
        and candidate["completed"]
        and candidate["effect_valid"]
    ]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda candidate: (
            candidate["unknown_constraints"],
            candidate["unresolved_constraints"],
            -candidate["satisfied_constraints"],
            candidate["candidate_index"],
        ),
    )


def classify_case(
    *,
    generation: dict[str, Any] | None,
    evaluation: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
) -> tuple[str | None, str]:
    if evaluation is not None and evaluation.get("official_pass") is True:
        return "success", "official evaluator passed"

    episode = (
        generation.get("metadata", {}).get("episode", {})
        if generation is not None
        else {}
    )
    if not isinstance(episode, dict):
        episode = {}
    if (
        evaluation is not None
        and evaluation.get("evaluation_completed") is True
        and episode.get("candidate_certification") == "certified"
    ):
        return "evaluator_gap", "internally certified candidate failed official evaluation"

    best = best_complete_candidate(candidates)
    if best is not None:
        if best["unknown_constraints"] > 0:
            return "observability_gap", "best complete candidate retained unknown constraints"
        if best["unresolved_constraints"] > 0:
            return "closure_gap", "best complete candidate retained active constraints"
        if episode.get("candidate_certification") == "certified":
            return None, "internal certification has no completed official evaluation"

    if generation is None:
        return None, "generation is incomplete"
    if not candidates and generation.get("error"):
        return None, "generation failed before a candidate verification"
    return "operation_nonviability", "no complete zero-exit effect-valid candidate"


def analyze_case(case_id: str, run_root: Path) -> dict[str, Any]:
    case_root = run_root / safe_name(case_id)
    generation = _read_json(case_root / "generation/result.json")
    evaluation = _read_json(case_root / "evaluation/result.json")
    episode_path = case_root / "generation/episode.jsonl"
    events = read_jsonl(episode_path) if episode_path.is_file() else []
    candidates = candidate_verifications(events)
    category, reason = classify_case(
        generation=generation,
        evaluation=evaluation,
        candidates=candidates,
    )
    exit_counts = Counter(
        str(candidate["bootstrap_exit_code"]) for candidate in candidates
    )
    best = best_complete_candidate(candidates)
    episode = (
        generation.get("metadata", {}).get("episode", {})
        if generation is not None
        else {}
    )
    return {
        "case_id": case_id,
        "artifact_root": str(case_root),
        "scientifically_complete": category is not None,
        "category": category,
        "classification_reason": reason,
        "generation_finished": generation is not None,
        "evaluation_finished": evaluation is not None,
        "official_pass": evaluation.get("official_pass") if evaluation else None,
        "candidate_certification": (
            episode.get("candidate_certification")
            if isinstance(episode, dict)
            else None
        ),
        "candidate_statistics": {
            "verified_candidates": len(candidates),
            "bootstrap_exit_code_counts": dict(sorted(exit_counts.items())),
            "execution_timeouts": sum(
                candidate["bootstrap_exit_code"] == 124 for candidate in candidates
            ),
            "effect_audit_failures": sum(
                candidate["bootstrap_exit_code"] == 0
                and candidate["completed"]
                and not candidate["effect_valid"]
                for candidate in candidates
            ),
            "complete_zero_exit_effect_valid": sum(
                candidate["bootstrap_exit_code"] == 0
                and candidate["completed"]
                and candidate["effect_valid"]
                for candidate in candidates
            ),
            "internally_reported_passed": sum(
                candidate["reported_passed"] for candidate in candidates
            ),
        },
        "best_complete_candidate": best,
    }


def aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    classified = [case for case in cases if case["scientifically_complete"]]
    counts = Counter(case["category"] for case in classified)
    category_counts = {category: counts.get(category, 0) for category in CATEGORIES}
    denominator = len(classified)
    shares = {
        category: (category_counts[category] / denominator if denominator else None)
        for category in CATEGORIES
    }
    max_count = max(category_counts.values(), default=0)
    leaders = [
        category for category, count in category_counts.items() if count == max_count
    ]
    dominant = (
        leaders[0]
        if denominator == len(cases) and max_count > 0 and len(leaders) == 1
        else None
    )
    operation_or_closure = (
        category_counts["operation_nonviability"] + category_counts["closure_gap"]
    )
    return {
        "expected_cases": len(cases),
        "scientifically_complete_cases": denominator,
        "category_counts": category_counts,
        "category_shares": shares,
        "dominant_contradiction": dominant,
        "dominant_contradiction_resolved": dominant is not None,
        "prediction": {
            "operation_or_closure_strict_majority": (
                operation_or_closure > denominator / 2 if denominator else None
            )
        },
        "candidate_totals": {
            key: sum(case["candidate_statistics"][key] for case in cases)
            for key in (
                "verified_candidates",
                "execution_timeouts",
                "effect_audit_failures",
                "complete_zero_exit_effect_valid",
                "internally_reported_passed",
            )
        },
    }


def main() -> int:
    args = parse_args()
    cases = read_jsonl(args.case_file.resolve())
    case_ids = [str(case["case_id"]) for case in cases]
    per_case = [analyze_case(case_id, args.run_root.resolve()) for case_id in case_ids]
    payload = {
        "schema_version": "1.0.0",
        "study_id": "envsolve-pro-trajectory-census-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case_file": str(args.case_file.resolve()),
        "run_root": str(args.run_root.resolve()),
        "aggregate": aggregate(per_case),
        "cases": per_case,
    }
    write_json(args.output.resolve(), payload)
    summary = payload["aggregate"]
    print(
        f"complete={summary['scientifically_complete_cases']}/{summary['expected_cases']} "
        f"dominant={summary['dominant_contradiction']}"
    )
    print(f"output={args.output.resolve()}")
    return 0 if summary["scientifically_complete_cases"] == len(per_case) else 2


if __name__ == "__main__":
    raise SystemExit(main())
