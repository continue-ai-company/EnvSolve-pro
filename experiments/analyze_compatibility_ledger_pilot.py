#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from statistics import median
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.storage.artifacts import safe_name


EXPECTED_MODEL = "deepseek/deepseek-v4-flash-0731"
EXPECTED_PROVIDER_ORDER = ["deepinfra"]
EXPECTED_RETURNED_PROVIDER = "DeepInfra"
EFFICIENCY_METRICS = (
    "model_requests",
    "interactive_tool_steps",
    "total_tokens",
    "seconds_to_certificate",
)


def _events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if isinstance(value, dict):
            result.append(value)
    return result


def _candidate_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in events:
        if event.get("event") != "tool_result":
            continue
        if event.get("tool_name") != "submit_and_replay":
            continue
        result = event.get("result")
        if not isinstance(result, dict) or result.get("status") != "pass":
            continue
        certificate = result.get("certificate")
        if not isinstance(certificate, dict):
            continue
        digest = result.get("program_sha256")
        if digest and digest == certificate.get("program_sha256"):
            return event
    return None


def _usage(events: list[dict[str, Any]], boundary: int | None) -> dict[str, Any]:
    totals = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
        "cost": 0.0,
    }
    requests = 0
    for event in events:
        if event.get("event") != "provider_response":
            continue
        request_index = event.get("request_index")
        if boundary is not None and isinstance(request_index, int):
            if request_index > boundary:
                continue
        response = event.get("response")
        usage = response.get("usage") if isinstance(response, dict) else None
        usage = usage if isinstance(usage, dict) else {}
        details = usage.get("completion_tokens_details")
        details = details if isinstance(details, dict) else {}
        requests += 1
        totals["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
        totals["completion_tokens"] += int(usage.get("completion_tokens") or 0)
        totals["reasoning_tokens"] += int(details.get("reasoning_tokens") or 0)
        totals["total_tokens"] += int(usage.get("total_tokens") or 0)
        totals["cost"] += float(usage.get("cost") or 0.0)
    return {"model_requests": requests, **totals}


def _seconds_between(start: Any, end: Any) -> float | None:
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    try:
        return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
    except ValueError:
        return None


def _terminal_provider_failure(events: list[dict[str, Any]]) -> bool:
    successful_requests = {
        event.get("request_index")
        for event in events
        if event.get("event") == "provider_response"
    }
    return any(
        event.get("event") == "provider_error"
        and event.get("next_retry_delay_seconds") is None
        and event.get("request_index") not in successful_requests
        for event in events
    )


def _episode(run_root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    case_root = run_root / safe_name(spec["run_id"]) / safe_name(spec["case_id"])
    manifest_path = case_root / "manifest.json"
    manifest = read_json(manifest_path) if manifest_path.is_file() else {}
    solver = manifest.get("solver") if isinstance(manifest, dict) else None
    solver = solver if isinstance(solver, dict) else {}
    metadata = solver.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    result = manifest.get("result") if isinstance(manifest, dict) else None
    result = result if isinstance(result, dict) else {}
    trajectory = case_root / str(
        solver.get("trajectory_path") or "generation/trajectory.jsonl"
    )
    events = _events(trajectory)
    provider_responses = [
        event for event in events if event.get("event") == "provider_response"
    ]
    provider_events = [
        event
        for event in events
        if event.get("event") in {"provider_response", "provider_error"}
    ]
    candidate = _candidate_event(events)
    boundary = candidate.get("request_index") if candidate is not None else None
    boundary = boundary if isinstance(boundary, int) else None
    certificate = (
        candidate.get("result", {}).get("certificate", {})
        if candidate is not None
        else {}
    )
    started_at = metadata.get("started_at")
    certified_at = (
        certificate.get("certified_at") if isinstance(certificate, dict) else None
    )
    through = _usage(events, boundary)
    through["interactive_tool_steps"] = sum(
        event.get("event") == "tool_result"
        and event.get("tool_name") in {"envbench_shell", "check_compatibility"}
        and (boundary is None or int(event.get("request_index") or 0) <= boundary)
        for event in events
    )
    through["seconds_to_certificate"] = _seconds_between(started_at, certified_at)

    checks = [
        event.get("result")
        for event in events
        if event.get("event") == "tool_result"
        and event.get("tool_name") == "check_compatibility"
        and isinstance(event.get("result"), dict)
    ]
    recorded_orders = {
        tuple(
            (
                event.get("request_contract", {}).get("provider", {}).get("order")
                or []
            )
        )
        for event in provider_events
    }
    returned_providers = {
        event.get("response", {}).get("provider")
        for event in provider_responses
        if isinstance(event.get("response"), dict)
    }
    returned_models = {
        event.get("response", {}).get("model")
        for event in provider_responses
        if isinstance(event.get("response"), dict)
    }
    complete = solver.get("generation_completed") is not None
    terminal_provider_failure = _terminal_provider_failure(events)
    censored = not manifest_path.is_file() or not complete or terminal_provider_failure
    errors = []
    if provider_events and recorded_orders != {tuple(EXPECTED_PROVIDER_ORDER)}:
        errors.append("provider-order-mismatch")
    if provider_responses and returned_providers != {EXPECTED_RETURNED_PROVIDER}:
        errors.append("returned-provider-mismatch")
    if provider_responses and returned_models != {EXPECTED_MODEL}:
        errors.append("returned-model-mismatch")
    if terminal_provider_failure:
        errors.append("terminal-provider-failure")
    if not manifest_path.is_file():
        errors.append("manifest-missing")
    if not complete:
        errors.append("episode-incomplete")

    official = result.get("official_pass")
    if not censored and official is not True:
        official = False
    ledger = metadata.get("compatibility_ledger")
    ledger = ledger if isinstance(ledger, dict) else {}
    return {
        "position": spec.get("original_position", spec["position"]),
        "run_id": spec["run_id"],
        "case_id": spec["case_id"],
        "pair_id": spec["pair_id"],
        "replication": spec["replication"],
        "arm": spec["arm"],
        "artifact_root": str(case_root.resolve()),
        "censored": censored,
        "validity_errors": errors,
        "generation_completed": solver.get("generation_completed"),
        "generation_error": solver.get("error"),
        "candidate_formed": candidate is not None,
        "candidate_request_index": boundary,
        "official_evaluation_completed": result.get("evaluation_completed"),
        "official_pass": official,
        "pre_candidate": through,
        "total": {
            "model_requests": len(provider_responses),
            "provider_errors": sum(
                event.get("event") == "provider_error" for event in events
            ),
            "interactive_tool_steps": sum(
                event.get("event") == "tool_result"
                and event.get("tool_name")
                in {"envbench_shell", "check_compatibility"}
                for event in events
            ),
            "token_usage": metadata.get("token_usage"),
            "generation_seconds": _seconds_between(
                started_at, metadata.get("finished_at")
            ),
            "official_evaluation_seconds": result.get("execution_time"),
        },
        "provider": {
            "recorded_orders": [list(item) for item in sorted(recorded_orders)],
            "returned": sorted(str(item) for item in returned_providers),
            "models": sorted(str(item) for item in returned_models),
        },
        "mechanism": {
            "check_count": len(checks),
            "complete_check_count": sum(
                item.get("ok") is True
                and item.get("finding_set_complete") is True
                for item in checks
            ),
            "unknown_check_count": sum(item.get("ok") is False for item in checks),
            "candidate_ready_count": sum(
                item.get("candidate_ready") is True for item in checks
            ),
            "operation_constraint_violations": sum(
                item.get("operation_constraints_added") is not False for item in checks
            ),
            "ledger_metadata": ledger,
        },
    }


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
        control = values.get("B-FSR")
        treatment = values.get("D-LEDGER")
        pair = {
            "pair_id": pair_id,
            "complete": control is not None and treatment is not None,
            "B-FSR": control,
            "D-LEDGER": treatment,
            "treatment_only_official_win": False,
            "treatment_only_official_loss": False,
            "comparable_success": False,
            "resource_ratios_D_over_B": {},
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
                            pair["resource_ratios_D_over_B"][metric] = (
                                numerator / denominator
                            )
        result.append(pair)
    return result


def _adjudicate(records: list[dict[str, Any]], pairs: list[dict[str, Any]]) -> dict[str, Any]:
    treatment = [
        item for item in records if item["arm"] == "D-LEDGER" and not item["censored"]
    ]
    checks = sum(item["mechanism"]["check_count"] for item in treatment)
    complete_checks = sum(
        item["mechanism"]["complete_check_count"] for item in treatment
    )
    transitions: dict[str, int] = {}
    for item in treatment:
        counts = item["mechanism"]["ledger_metadata"].get("transition_counts", {})
        if isinstance(counts, dict):
            for name, count in counts.items():
                transitions[str(name)] = transitions.get(str(name), 0) + int(count)
    comparable_transitions = sum(
        count for name, count in transitions.items() if name != "initial"
    )
    changed_transitions = sum(
        transitions.get(name, 0) for name in ("improved", "regressed", "mixed")
    )
    mechanism_pass = (
        len(treatment) == 4
        and all(item["mechanism"]["check_count"] >= 1 for item in treatment)
        and checks > 0
        and complete_checks / checks >= 0.75
        and comparable_transitions >= 2
        and changed_transitions >= 1
        and sum(
            item["mechanism"]["operation_constraint_violations"] for item in treatment
        )
        == 0
        and all(
            item["mechanism"]["ledger_metadata"].get("stores_container_checkpoint")
            is False
            for item in treatment
        )
    )

    ratios: dict[str, float] = {}
    for metric in EFFICIENCY_METRICS:
        values = [
            pair["resource_ratios_D_over_B"][metric]
            for pair in pairs
            if metric in pair["resource_ratios_D_over_B"]
        ]
        if values:
            ratios[metric] = median(values)
    efficiency_signal = (
        bool(ratios)
        and sum(value <= 0.85 for value in ratios.values()) >= 2
        and all(value <= 1.15 for value in ratios.values())
    )
    control = _arm_summary(records, "B-FSR")
    ledger = _arm_summary(records, "D-LEDGER")
    wins = sum(pair["treatment_only_official_win"] for pair in pairs)
    losses = sum(pair["treatment_only_official_loss"] for pair in pairs)
    complete = len(records) == 8 and not any(item["censored"] for item in records)
    directional = (
        ledger["candidate_formed"] >= control["candidate_formed"]
        and ledger["official_pass"] >= control["official_pass"]
        and losses <= 1
        and (wins >= 1 or efficiency_signal)
    )
    if not complete:
        decision = "incomplete-or-censored"
    elif not mechanism_pass:
        decision = "negative-mechanism-not-qualified"
    elif directional:
        decision = "positive-directional-promote-to-broader-consumed-study"
    elif (
        ledger["candidate_formed"] < control["candidate_formed"]
        or ledger["official_pass"] < control["official_pass"]
        or losses > 1
    ):
        decision = "negative-directional-do-not-expose-frozen-dev"
    else:
        decision = "ambiguous-preregister-broader-consumed-study-unchanged"
    return {
        "decision": decision,
        "mechanism_acceptance": {
            "passed": mechanism_pass,
            "treatment_episode_count": len(treatment),
            "check_count": checks,
            "complete_check_rate": complete_checks / checks if checks else None,
            "transition_counts": transitions,
            "comparable_transition_count": comparable_transitions,
            "changed_transition_count": changed_transitions,
        },
        "directional": {
            "arms": {"B-FSR": control, "D-LEDGER": ledger},
            "treatment_only_official_wins": wins,
            "treatment_only_official_losses": losses,
            "median_paired_resource_ratios_D_over_B": ratios,
            "efficiency_signal": efficiency_signal,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze the frozen ledger pilot.")
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--replacement-schedule", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    schedule = read_json(args.schedule.resolve())
    replacement = read_json(args.replacement_schedule.resolve())["episodes"][0]
    specs = [
        replacement if int(item["position"]) == 1 else item
        for item in schedule["episodes"]
    ]
    records = [_episode(args.run_root.resolve(), item) for item in specs]
    pairs = _pairs(records)
    output = {
        "schema": "envsolve-pro-v2-compatibility-ledger-pilot-analysis-v1",
        "analysis_contract": (
            "experiments/validations/"
            "envsolve_pro_v2_compatibility_ledger_pilot_v1_analysis_contract.json"
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
