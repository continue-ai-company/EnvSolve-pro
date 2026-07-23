#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import read_jsonl, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare EnvSolve internal import obligations with the official objective."
    )
    parser.add_argument("--run-root", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--study-id", required=True)
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else None


def _string_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str) and item}


def _official_missing_modules(evaluation: dict[str, Any]) -> set[str]:
    for evidence in evaluation.get("evidence") or []:
        if not isinstance(evidence, dict):
            continue
        metrics = evidence.get("metrics")
        if (
            evidence.get("verifier_id") == "envbench-pyright-diagnostic"
            and isinstance(metrics, dict)
        ):
            return _string_set(metrics.get("missing_import_modules"))
    return set()


def _accepted_candidate_id(generation: dict[str, Any]) -> str | None:
    episode = (generation.get("metadata") or {}).get("episode") or {}
    accepted = episode.get("accepted_candidate") or {}
    candidate_id = accepted.get("candidate_id")
    return candidate_id if isinstance(candidate_id, str) else None


def _accepted_verification(
    events: Iterable[dict[str, Any]],
    candidate_id: str,
) -> dict[str, Any] | None:
    selected = None
    for event in events:
        if event.get("event_type") != "verification_recorded":
            continue
        payload = event.get("payload")
        details = payload.get("details") if isinstance(payload, dict) else None
        if isinstance(details, dict) and details.get("candidate_id") == candidate_id:
            selected = details
    return selected


def analyze_case(case_root: Path) -> dict[str, Any]:
    manifest = _read_json(case_root / "manifest.json") or {}
    generation = _read_json(case_root / "generation/result.json")
    evaluation = _read_json(case_root / "evaluation/result.json")
    case = manifest.get("case") or {}
    record: dict[str, Any] = {
        "case_id": case.get("case_id"),
        "repository": case.get("repository"),
        "artifact_root": str(case_root.resolve()),
        "complete": False,
    }
    if generation is None or evaluation is None:
        record["incomplete_reason"] = "generation or evaluation result missing"
        return record

    candidate_id = _accepted_candidate_id(generation)
    episode_path = case_root / "generation/episode.jsonl"
    if candidate_id is None or not episode_path.is_file():
        record["incomplete_reason"] = "accepted candidate verification missing"
        return record
    verification = _accepted_verification(read_jsonl(episode_path), candidate_id)
    if verification is None:
        record["incomplete_reason"] = "accepted candidate event not found"
        return record

    verifier = verification.get("verifier_details") or {}
    report = verifier.get("report_details") or {}
    assessment = verification.get("candidate_assessment") or {}
    static_modules = _string_set(report.get("static_unresolved_modules"))
    runtime_modules = _string_set(report.get("runtime_unresolved_modules"))
    official_modules = _official_missing_modules(evaluation)
    internal_modules = static_modules | runtime_modules
    overlap = static_modules & official_modules
    excess = internal_modules - official_modules
    official_unobserved = official_modules - static_modules
    raw_metrics = evaluation.get("raw_metrics") or {}

    record.update(
        {
            "complete": True,
            "candidate_id": candidate_id,
            "official_pass": evaluation.get("official_pass"),
            "official_issues_count": raw_metrics.get("issues_count"),
            "official_missing_modules": sorted(official_modules),
            "static_unresolved_modules": sorted(static_modules),
            "runtime_unresolved_modules": sorted(runtime_modules),
            "runtime_only_modules": sorted(runtime_modules - static_modules),
            "official_static_overlap": sorted(overlap),
            "official_unobserved_modules": sorted(official_unobserved),
            "excess_internal_modules": sorted(excess),
            "internal_unresolved_constraints": int(
                assessment.get("unresolved_constraints", 0) or 0
            ),
            "module_obligation_counts": {
                "official": len(official_modules),
                "static": len(static_modules),
                "runtime": len(runtime_modules),
                "internal_union": len(internal_modules),
                "official_static_overlap": len(overlap),
                "official_unobserved": len(official_unobserved),
                "excess_internal": len(excess),
                "runtime_only": len(runtime_modules - static_modules),
            },
            "objective_dilution_ratio": (
                len(excess) / len(internal_modules) if internal_modules else 0.0
            ),
        }
    )
    return record


def aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    complete = [case for case in cases if case["complete"]]
    official_total = sum(
        case["module_obligation_counts"]["official"] for case in complete
    )
    overlap_total = sum(
        case["module_obligation_counts"]["official_static_overlap"]
        for case in complete
    )
    internal_total = sum(
        case["module_obligation_counts"]["internal_union"] for case in complete
    )
    excess_total = sum(
        case["module_obligation_counts"]["excess_internal"] for case in complete
    )
    return {
        "expected_cases": len(cases),
        "complete_cases": len(complete),
        "official_pass_cases": sum(case["official_pass"] is True for case in complete),
        "cases_with_official_unobserved_modules": sum(
            bool(case["official_unobserved_modules"]) for case in complete
        ),
        "cases_with_excess_internal_modules": sum(
            bool(case["excess_internal_modules"]) for case in complete
        ),
        "cases_with_runtime_only_modules": sum(
            bool(case["runtime_only_modules"]) for case in complete
        ),
        "cases_official_pass_despite_internal_unresolved": sum(
            case["official_pass"] is True
            and case["internal_unresolved_constraints"] > 0
            for case in complete
        ),
        "official_missing_module_total": official_total,
        "official_static_overlap_total": overlap_total,
        "static_proxy_recall": (
            overlap_total / official_total if official_total else None
        ),
        "internal_module_obligation_total": internal_total,
        "excess_internal_module_total": excess_total,
        "excess_internal_share": (
            excess_total / internal_total if internal_total else None
        ),
    }


def select_case_attempts(attempts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for attempt in attempts:
        key = str(attempt.get("case_id") or attempt["artifact_root"])
        grouped.setdefault(key, []).append(attempt)

    selected = []
    for case_attempts in grouped.values():
        choice = next(
            (attempt for attempt in case_attempts if attempt["complete"]),
            case_attempts[-1],
        )
        record = dict(choice)
        record["attempt_resolution"] = {
            "attempt_count": len(case_attempts),
            "selected_artifact_root": choice["artifact_root"],
            "artifacts": [
                {
                    "artifact_root": attempt["artifact_root"],
                    "complete": attempt["complete"],
                    "incomplete_reason": attempt.get("incomplete_reason"),
                }
                for attempt in case_attempts
            ],
        }
        selected.append(record)
    return selected


def main() -> int:
    args = parse_args()
    run_roots = [path.resolve() for path in args.run_root]
    case_roots = [
        case_root
        for run_root in run_roots
        for case_root in sorted(run_root.iterdir())
        if case_root.is_dir() and (case_root / "manifest.json").is_file()
    ]
    cases = select_case_attempts(analyze_case(case_root) for case_root in case_roots)
    payload = {
        "schema_version": "1.0.0",
        "study_id": args.study_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim_scope": "Consumed development trajectory diagnostics only",
        "run_roots": [str(path) for path in run_roots],
        "aggregate": aggregate(cases),
        "cases": cases,
    }
    write_json(args.output.resolve(), payload)
    summary = payload["aggregate"]
    print(
        f"complete={summary['complete_cases']}/{summary['expected_cases']} "
        f"recall={summary['static_proxy_recall']} "
        f"excess_share={summary['excess_internal_share']}"
    )
    print(f"output={args.output.resolve()}")
    return 0 if summary["complete_cases"] == summary["expected_cases"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
