#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import median
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import write_json
from envsolve_harness.results_v2 import _paired_aggregate_v2, summarize_schedule
from experiments.summarize_schedule_v2 import _attach_coordinator_progress


ARM_METHODS = {
    "F": "free-feedback-search-repository-signals",
    "F+O": "free-feedback-search-public-goal",
    "F+O+R": "envsolve-pro-fsr-minimal-h",
}
CONTRASTS = {
    "public_goal": ("F+O", "F"),
    "target_state_replay": ("F+O+R", "F+O"),
}
RESOURCE_METRICS = (
    "requests_started",
    "total_tokens",
    "elapsed_wall_clock_seconds",
    "commands",
)
REPLAY_TRACE_CANDIDATES = (
    Path("generation/clean-replay/replays.jsonl"),
    Path("generation/minimal-b/replays.jsonl"),
)


def _replay_mechanism(
    artifact_root: Path,
    *,
    replay_exposed: bool,
    official_pass: bool | None,
) -> dict[str, Any]:
    trace_path = next(
        (
            artifact_root / relative
            for relative in REPLAY_TRACE_CANDIDATES
            if (artifact_root / relative).is_file()
        ),
        None,
    )
    records = []
    if trace_path is not None:
        records = [
            json.loads(line)
            for line in trace_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    statuses = [str(record.get("status", "unknown")) for record in records]
    hashes = [record.get("program_sha256") for record in records]
    fail_to_pass = any(
        status == "fail" and "pass" in statuses[index + 1 :]
        for index, status in enumerate(statuses)
    )
    changed_after_failure = any(
        status == "fail"
        and isinstance(hashes[index], str)
        and any(
            isinstance(later, str) and later != hashes[index]
            for later in hashes[index + 1 :]
        )
        for index, status in enumerate(statuses)
    )
    final_status = statuses[-1] if statuses else None
    agreement = None
    if isinstance(official_pass, bool) and final_status in {"pass", "fail"}:
        agreement = (final_status == "pass") is official_pass
    return {
        "replay_exposed": replay_exposed,
        "replay_activated": bool(records),
        "replay_count": len(records),
        "statuses": statuses,
        "first_replay_status": statuses[0] if statuses else None,
        "first_replay_certification": statuses[:1] == ["pass"],
        "fail_to_pass_repair": fail_to_pass,
        "program_changed_after_failure": changed_after_failure,
        "final_replay_status": final_status,
        "final_replay_official_agreement": agreement,
        "trace_path": (
            str(trace_path.relative_to(artifact_root)) if trace_path is not None else None
        ),
    }


def _attach_replay_mechanisms(
    runs: list[dict[str, Any]],
    runs_root: Path,
) -> None:
    for run in runs:
        artifact_root = runs_root / str(run["artifact_root"])
        run["replay_mechanism"] = _replay_mechanism(
            artifact_root,
            replay_exposed=run.get("method") == ARM_METHODS["F+O+R"],
            official_pass=run.get("official_pass"),
        )


def _numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _aggregate_values(values: list[int | float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "sum": sum(values),
        "median": median(values),
        "min": min(values),
        "max": max(values),
    }


def _arm_summary(runs: list[dict[str, Any]], method: str) -> dict[str, Any]:
    selected = [run for run in runs if run.get("method") == method]
    eligible = [run for run in selected if run.get("scientifically_eligible") is True]
    resources: dict[str, Any] = {}
    for metric in RESOURCE_METRICS:
        values = [
            run["resources"][metric]
            for run in selected
            if isinstance(run.get("resources"), dict)
            and _numeric(run["resources"].get(metric))
        ]
        resources[metric] = _aggregate_values(values) if values else None
    replay = [
        (run, run["replay_mechanism"])
        for run in selected
        if isinstance(run.get("replay_mechanism"), dict)
    ]
    measured_agreement = [
        item["final_replay_official_agreement"]
        for run, item in replay
        if run.get("scientifically_eligible") is True
        and isinstance(item.get("final_replay_official_agreement"), bool)
    ]
    return {
        "method": method,
        "runs": len(selected),
        "scientifically_eligible": len(eligible),
        "official_pass": sum(run.get("official_pass") is True for run in eligible),
        "official_fail": sum(run.get("official_pass") is False for run in eligible),
        "terminal_counts": dict(
            sorted(Counter(str(run.get("descriptive_terminal")) for run in selected).items())
        ),
        "replay_mechanism": {
            "exposed": sum(
                item.get("replay_exposed") is True for _, item in replay
            ),
            "activated": sum(
                item.get("replay_activated") is True for _, item in replay
            ),
            "first_replay_certification": sum(
                item.get("first_replay_certification") is True for _, item in replay
            ),
            "fail_to_pass_repair": sum(
                item.get("fail_to_pass_repair") is True for _, item in replay
            ),
            "program_changed_after_failure": sum(
                item.get("program_changed_after_failure") is True for _, item in replay
            ),
            "replay_official_agreement": {
                "measured": len(measured_agreement),
                "agrees": sum(measured_agreement),
            },
        },
        "resources_all_runs": resources,
    }


def _common_success_resources(
    runs: list[dict[str, Any]],
    treatment_method: str,
    control_method: str,
) -> dict[str, Any]:
    pairs: dict[str, dict[str, dict[str, Any]]] = {}
    for run in runs:
        pair_id = run.get("pair_id")
        if not isinstance(pair_id, str) or not pair_id:
            continue
        pairs.setdefault(pair_id, {})[str(run.get("method"))] = run

    common = []
    for pair_id, methods in pairs.items():
        treatment = methods.get(treatment_method)
        control = methods.get(control_method)
        if treatment is None or control is None:
            continue
        if not (
            treatment.get("scientifically_eligible") is True
            and control.get("scientifically_eligible") is True
            and treatment.get("official_pass") is True
            and control.get("official_pass") is True
        ):
            continue
        common.append((pair_id, treatment, control))

    metrics: dict[str, Any] = {}
    for metric in RESOURCE_METRICS:
        treatment_values: list[int | float] = []
        control_values: list[int | float] = []
        deltas: list[int | float] = []
        measured_pair_ids = []
        for pair_id, treatment, control in common:
            treatment_resources = treatment.get("resources") or {}
            control_resources = control.get("resources") or {}
            treatment_value = treatment_resources.get(metric)
            control_value = control_resources.get(metric)
            if not (_numeric(treatment_value) and _numeric(control_value)):
                continue
            treatment_values.append(treatment_value)
            control_values.append(control_value)
            deltas.append(treatment_value - control_value)
            measured_pair_ids.append(pair_id)
        metrics[metric] = {
            "measured_pairs": len(deltas),
            "pair_ids": measured_pair_ids,
            "treatment": _aggregate_values(treatment_values) if treatment_values else None,
            "control": _aggregate_values(control_values) if control_values else None,
            "treatment_minus_control": (
                _aggregate_values(deltas) if deltas else None
            ),
        }
    return {
        "common_success_pairs": len(common),
        "pair_ids": [pair_id for pair_id, _, _ in common],
        "metrics": metrics,
    }


def analyze(summary: dict[str, Any]) -> dict[str, Any]:
    runs = summary["runs"]
    arms = {
        arm: _arm_summary(runs, method)
        for arm, method in ARM_METHODS.items()
    }
    contrasts = {}
    for name, (treatment_arm, control_arm) in CONTRASTS.items():
        treatment_method = ARM_METHODS[treatment_arm]
        control_method = ARM_METHODS[control_arm]
        contrasts[name] = {
            "treatment_arm": treatment_arm,
            "control_arm": control_arm,
            "paired_official": _paired_aggregate_v2(
                runs,
                treatment_method,
                control_method,
                missing_official_as_failure=False,
            ),
            "paired_end_to_end": _paired_aggregate_v2(
                runs,
                treatment_method,
                control_method,
                missing_official_as_failure=True,
            ),
            "resources_on_common_success": _common_success_resources(
                runs,
                treatment_method,
                control_method,
            ),
        }
    return {
        "schema": "envsolve-pro-for-mechanism-analysis-v1",
        "claim_scope": "Consumed-development mechanism identification only",
        "primary_outcome": "Official Pass@1",
        "resource_interpretation": (
            "Secondary; compare arms on common-success pairs so early failure is not "
            "misreported as efficiency."
        ),
        "schedule": summary["schedule"],
        "descriptive": summary["descriptive"],
        "scientific": summary["scientific"],
        "arms": arms,
        "contrasts": contrasts,
        "coordinator_progress": summary.get("coordinator_progress"),
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze the fixed F/F+O/F+O+R mechanism schedule."
    )
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--progress", type=Path, action="append", default=[])
    args = parser.parse_args()

    summary = summarize_schedule(args.schedule, args.runs_root)
    _attach_replay_mechanisms(summary["runs"], args.runs_root.resolve())
    if args.progress:
        _attach_coordinator_progress(summary, args.progress)
    result = analyze(summary)
    write_json(args.output, result)
    print(f"analysis={args.output.resolve()}")
    print(
        " ".join(
            f"{arm}={values['official_pass']}/{values['scientifically_eligible']}"
            for arm, values in result["arms"].items()
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
