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

from envsolve_harness.core.io import read_json, write_json
from experiments.analyze_compatibility_ledger_pilot import (
    EFFICIENCY_METRICS,
    _apply_cross_arm_validity,
    _apply_replacement_schedules,
    _episode,
    _events,
)


CONTROL_ARM = "B-FSR"
TREATMENT_ARM = "E-SCHEDULED"
FROZEN_CADENCE = 16


def _scheduled_mechanism(
    events: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    indexed_observations = [
        (index, event)
        for index, event in enumerate(events)
        if event.get("event") == "compatibility_observation"
    ]
    shell_events = [
        (index, event)
        for index, event in enumerate(events)
        if event.get("event") == "tool_result"
        and event.get("tool_name") == "envbench_shell"
    ]
    replay_events = [
        (index, event)
        for index, event in enumerate(events)
        if event.get("event") == "tool_result"
        and event.get("tool_name") == "submit_and_replay"
    ]
    optional_tool_count = sum(
        event.get("event") == "tool_result"
        and event.get("tool_name") == "check_compatibility"
        for event in events
    )
    trigger_counts = Counter(
        str(event.get("trigger")) for _, event in indexed_observations
    )
    errors: list[str] = []

    initial = [
        (index, event)
        for index, event in indexed_observations
        if event.get("trigger") == "initial"
    ]
    first_provider_index = next(
        (
            index
            for index, event in enumerate(events)
            if event.get("event") in {"provider_response", "provider_error"}
        ),
        len(events),
    )
    if len(initial) != 1:
        errors.append("initial-observation-count-mismatch")
    elif initial[0][0] >= first_provider_index or initial[0][1].get("request_index") != 0:
        errors.append("initial-observation-not-before-first-model-request")

    shell_count = len(shell_events)
    expected_periodic_counts = list(range(FROZEN_CADENCE, shell_count + 1, FROZEN_CADENCE))
    actual_periodic_counts = [
        event.get("shell_operations_completed")
        for _, event in indexed_observations
        if event.get("trigger") == "periodic"
    ]
    if actual_periodic_counts != expected_periodic_counts:
        errors.append("periodic-observation-schedule-mismatch")

    observation_by_call = {
        event.get("parent_tool_call_id"): (index, event)
        for index, event in indexed_observations
        if isinstance(event.get("parent_tool_call_id"), str)
    }
    for index, event in indexed_observations:
        trigger = event.get("trigger")
        if event.get("feedback_delivery") != "same-active-model-session":
            errors.append("feedback-delivery-mismatch")
        if trigger == "initial":
            continue
        parent = event.get("parent_tool_call_id")
        matching = [
            (tool_index, tool_event)
            for tool_index, tool_event in enumerate(events)
            if tool_index > index
            and tool_event.get("event") == "tool_result"
            and tool_event.get("tool_call_id") == parent
        ]
        if len(matching) != 1:
            errors.append("observation-parent-tool-result-mismatch")
            continue
        nested = matching[0][1].get("result")
        nested = nested if isinstance(nested, dict) else {}
        delivered = nested.get("scheduled_compatibility_observation")
        delivered = delivered if isinstance(delivered, dict) else {}
        if delivered.get("observation_number") != event.get("observation_number"):
            errors.append("observation-not-attached-to-parent-tool-result")

    previous_observation_shell_count = -1
    for _, event in indexed_observations:
        shell_position = event.get("shell_operations_completed")
        if not isinstance(shell_position, int):
            errors.append("observation-shell-count-missing")
            continue
        if event.get("trigger") == "pre-replay-dirty":
            if shell_position <= previous_observation_shell_count:
                errors.append("pre-replay-observation-without-dirty-state")
            parent = event.get("parent_tool_call_id")
            parent_event = observation_by_call.get(parent)
            if parent_event is None:
                errors.append("pre-replay-parent-missing")
        previous_observation_shell_count = shell_position

    for replay_index, replay in replay_events:
        shell_before_replay = sum(index < replay_index for index, _ in shell_events)
        prior_observations = [
            event for index, event in indexed_observations if index < replay_index
        ]
        latest_count = (
            prior_observations[-1].get("shell_operations_completed")
            if prior_observations
            else None
        )
        if latest_count != shell_before_replay:
            errors.append("dirty-replay-missing-current-observation")
        parent = replay.get("tool_call_id")
        matching_pre = [
            event
            for index, event in indexed_observations
            if index < replay_index
            and event.get("trigger") == "pre-replay-dirty"
            and event.get("parent_tool_call_id") == parent
        ]
        earlier_observation_counts = [
            event.get("shell_operations_completed")
            for index, event in indexed_observations
            if index < replay_index
            and not (
                event.get("trigger") == "pre-replay-dirty"
                and event.get("parent_tool_call_id") == parent
            )
            and isinstance(event.get("shell_operations_completed"), int)
        ]
        previous_count = earlier_observation_counts[-1] if earlier_observation_counts else -1
        pre_required = shell_before_replay > previous_count
        if pre_required != (len(matching_pre) == 1):
            errors.append("pre-replay-dirty-trigger-mismatch")

    complete_count = sum(
        isinstance(event.get("result"), dict)
        and event["result"].get("ok") is True
        and event["result"].get("finding_set_complete") is True
        for _, event in indexed_observations
    )
    operation_constraint_violations = sum(
        not isinstance(event.get("result"), dict)
        or event["result"].get("operation_constraints_added") is not False
        for _, event in indexed_observations
    )
    scheduled_metadata = metadata.get("scheduled_observation")
    scheduled_metadata = (
        scheduled_metadata if isinstance(scheduled_metadata, dict) else {}
    )
    if scheduled_metadata.get("schedule_compliant") is not True:
        errors.append("metadata-schedule-noncompliant")
    if scheduled_metadata.get("cadence_shell_operations") != FROZEN_CADENCE:
        errors.append("metadata-cadence-mismatch")
    if scheduled_metadata.get("observation_count") != len(indexed_observations):
        errors.append("metadata-observation-count-mismatch")
    if optional_tool_count:
        errors.append("optional-compatibility-tool-exposed-or-called")
    if scheduled_metadata.get("operation_constraints_added") is not False:
        errors.append("operation-constraints-added")
    if scheduled_metadata.get("stores_container_checkpoint") is not False:
        errors.append("container-checkpoint-stored")

    return {
        "event_observation_count": len(indexed_observations),
        "complete_observation_count": complete_count,
        "complete_observation_rate": (
            complete_count / len(indexed_observations)
            if indexed_observations
            else None
        ),
        "trigger_counts": dict(sorted(trigger_counts.items())),
        "shell_operation_count": shell_count,
        "replay_count": len(replay_events),
        "optional_tool_call_count": optional_tool_count,
        "operation_constraint_violations": operation_constraint_violations,
        "stores_container_checkpoint": scheduled_metadata.get(
            "stores_container_checkpoint"
        ),
        "schedule_compliant": not errors,
        "schedule_errors": sorted(set(errors)),
        "metadata": scheduled_metadata,
    }


def _enrich_mechanism(record: dict[str, Any]) -> None:
    case_root = Path(record["artifact_root"])
    manifest_path = case_root / "manifest.json"
    manifest = read_json(manifest_path) if manifest_path.is_file() else {}
    solver = manifest.get("solver") if isinstance(manifest, dict) else None
    solver = solver if isinstance(solver, dict) else {}
    metadata = solver.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    trajectory = case_root / str(
        solver.get("trajectory_path") or "generation/trajectory.jsonl"
    )
    record["mechanism"] = _scheduled_mechanism(_events(trajectory), metadata)


def _arm_summary(records: list[dict[str, Any]], arm: str) -> dict[str, Any]:
    selected = [item for item in records if item["arm"] == arm and not item["censored"]]
    return {
        "valid_episode_count": len(selected),
        "candidate_formed": sum(item["candidate_formed"] for item in selected),
        "official_pass": sum(item["official_pass"] is True for item in selected),
    }


def _pairs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for pair_id in sorted({item["pair_id"] for item in records}):
        values = {
            item["arm"]: item
            for item in records
            if item["pair_id"] == pair_id and not item["censored"]
        }
        control = values.get(CONTROL_ARM)
        treatment = values.get(TREATMENT_ARM)
        pair = {
            "pair_id": pair_id,
            "complete": control is not None and treatment is not None,
            CONTROL_ARM: control,
            TREATMENT_ARM: treatment,
            "treatment_only_official_win": False,
            "treatment_only_official_loss": False,
            "comparable_success": False,
            "resource_ratios_E_over_B": {},
        }
        if control is not None and treatment is not None:
            pair["treatment_only_official_win"] = (
                treatment["official_pass"] is True
                and control["official_pass"] is False
            )
            pair["treatment_only_official_loss"] = (
                treatment["official_pass"] is False
                and control["official_pass"] is True
            )
            comparable = all(
                item["candidate_formed"] and item["official_pass"] is True
                for item in (control, treatment)
            )
            pair["comparable_success"] = comparable
            if comparable:
                for metric in EFFICIENCY_METRICS:
                    denominator = control["pre_candidate"].get(metric)
                    numerator = treatment["pre_candidate"].get(metric)
                    if isinstance(denominator, (int, float)) and denominator > 0:
                        if isinstance(numerator, (int, float)):
                            pair["resource_ratios_E_over_B"][metric] = (
                                numerator / denominator
                            )
        result.append(pair)
    return result


def _adjudicate(
    records: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
) -> dict[str, Any]:
    treatment = [
        item
        for item in records
        if item["arm"] == TREATMENT_ARM and not item["censored"]
    ]
    observation_count = sum(
        item["mechanism"]["event_observation_count"] for item in treatment
    )
    complete_count = sum(
        item["mechanism"]["complete_observation_count"] for item in treatment
    )
    mechanism_pass = (
        len(treatment) == 8
        and all(item["mechanism"]["schedule_compliant"] for item in treatment)
        and observation_count > 0
        and complete_count / observation_count >= 0.75
        and all(
            item["mechanism"]["optional_tool_call_count"] == 0
            and item["mechanism"]["operation_constraint_violations"] == 0
            and item["mechanism"]["stores_container_checkpoint"] is False
            for item in treatment
        )
    )

    ratios: dict[str, float] = {}
    for metric in EFFICIENCY_METRICS:
        values = [
            pair["resource_ratios_E_over_B"][metric]
            for pair in pairs
            if metric in pair["resource_ratios_E_over_B"]
        ]
        if values:
            ratios[metric] = median(values)
    efficiency_signal = (
        bool(ratios)
        and sum(value <= 0.85 for value in ratios.values()) >= 2
        and all(value <= 1.15 for value in ratios.values())
    )
    control = _arm_summary(records, CONTROL_ARM)
    scheduled = _arm_summary(records, TREATMENT_ARM)
    wins = sum(pair["treatment_only_official_win"] for pair in pairs)
    losses = sum(pair["treatment_only_official_loss"] for pair in pairs)
    complete = len(records) == 16 and not any(item["censored"] for item in records)
    directional = (
        scheduled["official_pass"] >= control["official_pass"]
        and losses <= 1
        and (wins >= 1 or efficiency_signal)
    )
    if not complete:
        decision = "incomplete-or-censored"
    elif not mechanism_pass:
        decision = "negative-mechanism-not-qualified"
    elif directional:
        decision = "positive-directional-promote-to-frozen-dev-evaluation"
    elif scheduled["official_pass"] < control["official_pass"] or losses > 1:
        decision = "negative-directional-do-not-expose-frozen-dev"
    else:
        decision = "ambiguous-preregister-broader-consumed-study-unchanged"
    return {
        "decision": decision,
        "mechanism_acceptance": {
            "passed": mechanism_pass,
            "treatment_episode_count": len(treatment),
            "observation_count": observation_count,
            "complete_observation_rate": (
                complete_count / observation_count if observation_count else None
            ),
            "schedule_compliant_episode_count": sum(
                item["mechanism"]["schedule_compliant"] for item in treatment
            ),
        },
        "directional": {
            "arms": {CONTROL_ARM: control, TREATMENT_ARM: scheduled},
            "treatment_only_official_wins": wins,
            "treatment_only_official_losses": losses,
            "median_paired_resource_ratios_E_over_B": ratios,
            "efficiency_signal": efficiency_signal,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze the frozen scheduled-observation qualification."
    )
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--replacement-schedule",
        action="append",
        type=Path,
        default=[],
    )
    parser.add_argument(
        "--official-retry",
        action="append",
        default=[],
        metavar="SOURCE_RUN_ID=RETRY_RUN_ID",
    )
    args = parser.parse_args()
    schedule = read_json(args.schedule.resolve())
    specs = _apply_replacement_schedules(
        schedule["episodes"], args.replacement_schedule
    )
    retry_runs = {}
    for value in args.official_retry:
        source, separator, retry = value.partition("=")
        if not separator or not source or not retry or source in retry_runs:
            raise ValueError(f"Invalid or duplicate --official-retry mapping: {value}")
        retry_runs[source] = retry
    records = [
        _episode(
            args.run_root.resolve(),
            item,
            retry_runs.get(item["run_id"]),
        )
        for item in specs
    ]
    _apply_cross_arm_validity(records)
    for record in records:
        _enrich_mechanism(record)
    pairs = _pairs(records)
    output = {
        "schema": "envsolve-pro-v2-scheduled-observation-qualification-analysis-v1",
        "analysis_contract": (
            "experiments/validations/"
            "envsolve_pro_v2_scheduled_observation_qualification_v1_analysis_contract.json"
        ),
        "episodes": records,
        "pairs": pairs,
        "adjudication": _adjudicate(records, pairs),
    }
    write_json(args.output.resolve(), output)
    print(json.dumps(output["adjudication"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
