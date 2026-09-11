#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import median
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ruff: noqa: E402 - load workspace modules after adding the repository root.

from envsolve_harness.core.io import read_json, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate the fixed M1b replay screen.")
    parser.add_argument(
        "--schedule",
        type=Path,
        default=Path("experiments/schedules/envsolve_pro_m1b_artifact_replay_v1.json"),
    )
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path("runs/envsolve-pro-m1b-artifact-replay-v1"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "experiments/analyses/envsolve_pro_m1b_artifact_replay_result_20260911.json"
        ),
    )
    return parser.parse_args()


def classify_result(result: dict[str, Any]) -> str:
    status = result.get("status")
    if status == "pass":
        return "pass"
    if status == "not_started":
        return "not_started"
    if status == "infrastructure_error":
        error = str(result.get("infrastructure_error") or result.get("error") or "")
        if "dependency acquisition was interrupted by" in error:
            return "acquisition_failure"
        return "infrastructure_failure"

    verification = result.get("verification")
    verification = verification if isinstance(verification, dict) else {}
    bootstrap = verification.get("bootstrap")
    bootstrap = bootstrap if isinstance(bootstrap, dict) else {}
    if status == "fail" and bootstrap.get("exit_code") == 255:
        return "transport_failure"
    if status == "fail" and bootstrap.get("exit_code") == 42:
        return "interpreter_condition_mismatch"

    details = verification.get("details")
    details = details if isinstance(details, dict) else {}
    detail_text = str(details.get("json") or "")
    if status == "fail" and '"terminal_failure_origin": "verifier-condition"' in detail_text:
        return "interpreter_condition_mismatch"

    logs = "\n".join(
        str(bootstrap.get(key) or "") for key in ("stdout", "stderr")
    ).lower()
    if status == "fail" and any(
        marker in logs
        for marker in (
            "failed building wheel",
            "could not build wheels",
            "metadata-generation-failed",
            "no matching distribution found",
        )
    ):
        return "dependency_or_build_failure"
    if status == "fail" and bootstrap.get("exit_code") == 0:
        return "public_goal_failure"
    if status == "fail":
        return "execution_failure"
    return "missing_or_unknown"


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _summary(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "sum": sum(values),
        "median": median(values) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def _candidate_trials(
    project: dict[str, Any],
    run_root: Path,
) -> list[dict[str, Any]]:
    position = int(project["position"])
    candidates = {
        str(candidate["candidate_id"]): candidate
        for candidate in project["candidates"]
    }
    trials: list[dict[str, Any]] = []
    for round_record in project["rounds"]:
        round_index = int(round_record["round"])
        for order_index, candidate_id in enumerate(round_record["order"], start=1):
            result_path = (
                run_root
                / f"position{position}"
                / f"round{round_index}"
                / f"{order_index:02d}-{candidate_id}"
                / "result.json"
            )
            if result_path.exists():
                result = read_json(result_path)
                category = classify_result(result)
            else:
                result = {"status": "missing"}
                category = "missing_or_unknown"
            verification = result.get("verification")
            verification = verification if isinstance(verification, dict) else {}
            bootstrap = verification.get("bootstrap")
            bootstrap = bootstrap if isinstance(bootstrap, dict) else {}
            trials.append(
                {
                    "position": position,
                    "round": round_index,
                    "order_in_round": order_index,
                    "candidate_id": candidate_id,
                    "stage": candidates[candidate_id]["stage"],
                    "arm_aliases": candidates[candidate_id]["arm_aliases"],
                    "status": result.get("status"),
                    "category": category,
                    "replay_wall_seconds": _number(result.get("replay_wall_seconds")),
                    "bootstrap_seconds": _number(bootstrap.get("duration_seconds")),
                    "bootstrap_exit_code": bootstrap.get("exit_code"),
                    "infrastructure_error": result.get("infrastructure_error"),
                    "result_path": str(result_path.relative_to(ROOT)),
                }
            )
    return trials


def _candidate_summary(
    project: dict[str, Any],
    trials: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for candidate in project["candidates"]:
        candidate_id = str(candidate["candidate_id"])
        selected = [trial for trial in trials if trial["candidate_id"] == candidate_id]
        summaries.append(
            {
                "candidate_id": candidate_id,
                "stage": candidate["stage"],
                "arm_aliases": candidate["arm_aliases"],
                "physical_trials": len(selected),
                "category_counts": dict(
                    sorted(Counter(trial["category"] for trial in selected).items())
                ),
                "replay_wall_seconds": _summary(
                    [
                        trial["replay_wall_seconds"]
                        for trial in selected
                        if trial["replay_wall_seconds"] is not None
                    ]
                ),
                "bootstrap_seconds": _summary(
                    [
                        trial["bootstrap_seconds"]
                        for trial in selected
                        if trial["bootstrap_seconds"] is not None
                    ]
                ),
                "sources": candidate["sources"],
            }
        )
    return summaries


def _arm_final_summary(
    project: dict[str, Any],
    candidate_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    by_arm: dict[str, list[dict[str, Any]]] = {"P": [], "R0": [], "R1": []}
    for summary in candidate_summaries:
        if summary["stage"] != "final-submitted":
            continue
        for arm in summary["arm_aliases"]:
            by_arm[arm].append(summary)
    return {
        arm: {
            "artifact_count": len(summaries),
            "physical_measurements_shared_across_aliases": any(
                len(summary["arm_aliases"]) > 1 for summary in summaries
            ),
            "category_counts": dict(
                sorted(
                    sum(
                        (Counter(summary["category_counts"]) for summary in summaries),
                        Counter(),
                    ).items()
                )
            ),
        }
        for arm, summaries in by_arm.items()
    }


def _historical_generation_wall(run_id: str) -> float | None:
    matches = list(
        (ROOT / "runs/envsolve-pro-m1-project-progress-v1/mac-controller" / run_id).glob(
            "*/generation/result.json"
        )
    )
    if len(matches) != 1:
        return None
    metadata = read_json(matches[0]).get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    try:
        started = datetime.fromisoformat(str(metadata["started_at"]))
        finished = datetime.fromisoformat(str(metadata["finished_at"]))
    except (KeyError, TypeError, ValueError):
        return None
    return (finished - started).total_seconds()


def _d2_costs() -> dict[str, Any]:
    records = {
        10: ROOT / "experiments/validations/envsolve_pro_m1_position10_result_20260909.json",
        17: ROOT / "experiments/validations/envsolve_pro_m1_position17_result_20260910.json",
        22: ROOT / "experiments/validations/envsolve_pro_m1_position22_result_20260910.json",
        23: ROOT / "experiments/validations/envsolve_pro_m1_position23_result_20260910.json",
    }
    output: dict[str, Any] = {}
    for position, path in records.items():
        payload = read_json(path)
        rows = [
            row
            for key in ("valid_trials", "censored_trials")
            for row in payload.get(key, [])
            if row.get("condition") == "D2-adjacent-python"
        ]
        by_arm: dict[str, Any] = {}
        for row in rows:
            input_tokens = int(row.get("input_tokens") or 0)
            cached_tokens = int(row.get("cached_input_tokens") or 0)
            by_arm[str(row["arm"])] = {
                "run_id": row["run_id"],
                "input_tokens": input_tokens,
                "cached_input_tokens": cached_tokens,
                "uncached_input_tokens": input_tokens - cached_tokens,
                "output_tokens": int(row.get("output_tokens") or 0),
                "preflight_seconds": row.get("preflight_seconds"),
                "qualification_seconds": row.get("qualification_seconds"),
                "generation_episode_wall_seconds": _historical_generation_wall(
                    str(row["run_id"])
                ),
                "raw_official_status": row.get(
                    "raw_official_status",
                    "pass" if row.get("official_pass") is True else None,
                ),
                "raw_official_execution_seconds": row.get(
                    "official_execution_seconds"
                ),
                "historical_audit_valid": row.get("run_audit_valid", True),
            }
        output[str(position)] = by_arm
    return output


def _shared_d0_costs(schedule: dict[str, Any]) -> dict[str, Any]:
    source_schedule = read_json(
        ROOT / "experiments/schedules/envsolve_pro_m1_project_progress_v1.json"
    )
    output: dict[str, Any] = {}
    for project in source_schedule["projects"]:
        position = int(project["position"])
        source_run = ROOT / str(project["source_run"])
        matches = list(source_run.glob("*/generation/result.json"))
        result = read_json(matches[0]) if len(matches) == 1 else {}
        metadata = result.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        usage = metadata.get("token_usage")
        usage = usage if isinstance(usage, dict) else {}
        output[str(position)] = {
            "source_run": str(project["source_run"]),
            "shared_across_arms": True,
            "input_tokens": usage.get("input_tokens"),
            "cached_input_tokens": usage.get("cached_input_tokens"),
            "uncached_input_tokens": (
                usage.get("input_tokens") - usage.get("cached_input_tokens")
                if isinstance(usage.get("input_tokens"), int)
                and isinstance(usage.get("cached_input_tokens"), int)
                else None
            ),
            "output_tokens": usage.get("output_tokens"),
            "generation_episode_wall_seconds": _historical_generation_wall_from_result(
                result
            ),
        }
    return output


def _historical_generation_wall_from_result(result: dict[str, Any]) -> float | None:
    metadata = result.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    try:
        started = datetime.fromisoformat(str(metadata["started_at"]))
        finished = datetime.fromisoformat(str(metadata["finished_at"]))
    except (KeyError, TypeError, ValueError):
        return None
    return (finished - started).total_seconds()


def analyze(schedule_path: Path, run_root: Path) -> dict[str, Any]:
    schedule = read_json(schedule_path)
    projects: list[dict[str, Any]] = []
    all_trials: list[dict[str, Any]] = []
    for project in schedule["projects"]:
        trials = _candidate_trials(project, run_root)
        summaries = _candidate_summary(project, trials)
        all_trials.extend(trials)
        projects.append(
            {
                "position": project["position"],
                "case_id": project["case"]["case_id"],
                "fixed_q": {
                    "condition_id": project["condition_id"],
                    "python_version": project["python_version"],
                },
                "candidate_summaries": summaries,
                "final_artifacts_by_arm": _arm_final_summary(project, summaries),
                "trials": trials,
            }
        )

    categories = Counter(trial["category"] for trial in all_trials)
    return {
        "schema_version": "1.0.0",
        "study_id": schedule["study_id"],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "claim_scope": schedule["claim_scope"],
        "schedule": str(schedule_path.relative_to(ROOT)),
        "run_root": str(run_root.relative_to(ROOT)),
        "completion": {
            "scheduled_physical_replays": len(all_trials),
            "recorded_result_files": sum(
                trial["category"] != "missing_or_unknown" for trial in all_trials
            ),
            "category_counts": dict(sorted(categories.items())),
            "complete": all(
                trial["category"] != "missing_or_unknown" for trial in all_trials
            ),
        },
        "projects": projects,
        "costs": {
            "shared_d0_first_deployment": _shared_d0_costs(schedule),
            "historical_d2_update_and_validation": _d2_costs(),
            "m1b_replay_wall_seconds": _summary(
                [
                    trial["replay_wall_seconds"]
                    for trial in all_trials
                    if trial["replay_wall_seconds"] is not None
                ]
            ),
            "m1b_bootstrap_seconds": _summary(
                [
                    trial["bootstrap_seconds"]
                    for trial in all_trials
                    if trial["bootstrap_seconds"] is not None
                ]
            ),
            "m1b_model_tokens": 0,
            "counterfactual_future_repair_tokens": None,
            "empirical_break_even_count": None,
        },
        "claim_limits": schedule["claim_limits"],
        "protected_data_used": False,
    }


def main() -> int:
    args = parse_args()
    schedule_path = (ROOT / args.schedule).resolve()
    run_root = (ROOT / args.run_root).resolve()
    output_path = (ROOT / args.output).resolve()
    payload = analyze(schedule_path, run_root)
    write_json(output_path, payload)
    print(json.dumps(payload["completion"], sort_keys=True))
    return 0 if payload["completion"]["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
