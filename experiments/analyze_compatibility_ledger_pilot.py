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
from envsolve_harness.adapters.infrastructure import (
    envbench_evaluation_infrastructure_signature,
)
from envsolve_harness.audit import audit_run
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.utils.provenance import sha256_file


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


def _certification_evidence(result: dict[str, Any]) -> dict[str, Any] | None:
    raw_evidence = result.get("raw_evidence")
    for evidence in (raw_evidence, result):
        if not isinstance(evidence, dict):
            continue
        certificate = evidence.get("certificate")
        digest = evidence.get("program_sha256")
        if isinstance(certificate, dict) and isinstance(digest, str):
            return evidence
    return None


def _candidate_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in events:
        if event.get("event") != "tool_result":
            continue
        if event.get("tool_name") != "submit_and_replay":
            continue
        result = event.get("result")
        if not isinstance(result, dict) or result.get("status") != "pass":
            continue
        evidence = _certification_evidence(result)
        if evidence is None:
            continue
        certificate = evidence["certificate"]
        digest = evidence["program_sha256"]
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


def _candidate_ready_to_replay(events: list[dict[str, Any]]) -> dict[str, Any]:
    replay_requests = sorted(
        int(event["request_index"])
        for event in events
        if event.get("event") == "tool_result"
        and event.get("tool_name") == "submit_and_replay"
        and isinstance(event.get("request_index"), int)
    )
    measurements = []
    without_later_replay = 0
    for event in events:
        result = event.get("result")
        request_index = event.get("request_index")
        if (
            event.get("event") != "tool_result"
            or event.get("tool_name") != "check_compatibility"
            or not isinstance(result, dict)
            or result.get("candidate_ready") is not True
            or not isinstance(request_index, int)
        ):
            continue
        next_replay = next(
            (item for item in replay_requests if item >= request_index),
            None,
        )
        if next_replay is None:
            without_later_replay += 1
            continue
        measurements.append(
            {
                "candidate_ready_request_index": request_index,
                "next_replay_request_index": next_replay,
                "request_delta": next_replay - request_index,
            }
        )
    return {
        "measurements": measurements,
        "without_later_replay_count": without_later_replay,
    }


def _official_result(
    run_root: Path,
    case_root: Path,
    spec: dict[str, Any],
    retry_run_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    source_manifest = read_json(case_root / "manifest.json")
    source_result = source_manifest.get("result")
    source_result = source_result if isinstance(source_result, dict) else {}
    source_signature = envbench_evaluation_infrastructure_signature(source_result)
    provenance = {
        "source": "original-model-episode",
        "artifact_root": str(case_root.resolve()),
        "original_infrastructure_signature": source_signature,
        "retry_run_id": retry_run_id,
    }
    if retry_run_id is None:
        return source_result, provenance, []

    retry_root = run_root / safe_name(retry_run_id) / safe_name(spec["case_id"])
    retry_manifest_path = retry_root / "manifest.json"
    if not retry_manifest_path.is_file():
        return {}, provenance, ["official-retry-manifest-missing"]
    retry_manifest = read_json(retry_manifest_path)
    retry_solver = retry_manifest.get("solver")
    retry_solver = retry_solver if isinstance(retry_solver, dict) else {}
    retry_metadata = retry_solver.get("metadata")
    retry_metadata = retry_metadata if isinstance(retry_metadata, dict) else {}
    retry_binding = retry_metadata.get("evaluation_retry")
    retry_binding = retry_binding if isinstance(retry_binding, dict) else {}
    retry_result = retry_manifest.get("result")
    retry_result = retry_result if isinstance(retry_result, dict) else {}
    errors = []
    if source_signature is None:
        errors.append("official-retry-source-not-infrastructure-censored")
    if retry_binding.get("source_run_id") != spec["run_id"]:
        errors.append("official-retry-source-run-mismatch")
    if retry_binding.get("source_case_id") != spec["case_id"]:
        errors.append("official-retry-source-case-mismatch")
    source_script = case_root / "scripts/bootstrap.sh"
    if not source_script.is_file():
        errors.append("official-retry-source-script-missing")
    elif retry_binding.get("source_script_sha256") != sha256_file(source_script):
        errors.append("official-retry-script-hash-mismatch")
    retry_audit = audit_run(retry_root)
    if not retry_audit.valid:
        errors.append("official-retry-audit-invalid")
    provenance = {
        **provenance,
        "source": "exact-script-infrastructure-retry",
        "artifact_root": str(retry_root.resolve()),
        "retry_audit_valid": retry_audit.valid,
    }
    return retry_result, provenance, errors


def _episode(
    run_root: Path,
    spec: dict[str, Any],
    retry_run_id: str | None = None,
) -> dict[str, Any]:
    case_root = run_root / safe_name(spec["run_id"]) / safe_name(spec["case_id"])
    manifest_path = case_root / "manifest.json"
    manifest = read_json(manifest_path) if manifest_path.is_file() else {}
    solver = manifest.get("solver") if isinstance(manifest, dict) else None
    solver = solver if isinstance(solver, dict) else {}
    metadata = solver.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    result, official_provenance, official_retry_errors = _official_result(
        run_root, case_root, spec, retry_run_id
    ) if manifest_path.is_file() else ({}, {}, [])
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
    candidate_result = candidate.get("result") if candidate is not None else None
    candidate_result = candidate_result if isinstance(candidate_result, dict) else {}
    certification_evidence = _certification_evidence(candidate_result) or {}
    certificate = certification_evidence.get("certificate")
    certificate = certificate if isinstance(certificate, dict) else {}
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
    image_digest = metadata.get("image_digest")
    goal_contract = metadata.get("goal_contract")
    goal_contract = goal_contract if isinstance(goal_contract, dict) else {}
    goal_contract_sha256 = goal_contract.get("sha256")
    repository_integrity = metadata.get("repository_integrity")
    repository_integrity = (
        repository_integrity if isinstance(repository_integrity, dict) else {}
    )
    repository_integrity_invalid = (
        solver.get("generation_completed") is True
        and repository_integrity.get("valid") is not True
    )
    official_infrastructure_signature = (
        envbench_evaluation_infrastructure_signature(result) if result else None
    )
    official_evaluation_incomplete = (
        solver.get("generation_completed") is True
        and result.get("evaluation_completed") is not True
    )
    censored = (
        not manifest_path.is_file()
        or not complete
        or terminal_provider_failure
        or repository_integrity_invalid
        or official_evaluation_incomplete
        or bool(official_retry_errors)
    )
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
    if not isinstance(image_digest, str) or not image_digest:
        errors.append("image-digest-missing")
        censored = True
    if not isinstance(goal_contract_sha256, str) or not goal_contract_sha256:
        errors.append("goal-contract-hash-missing")
        censored = True
    if repository_integrity_invalid:
        errors.append("repository-integrity-invalid")
    if official_evaluation_incomplete:
        errors.append("official-evaluation-incomplete")
    if official_infrastructure_signature is not None:
        errors.append(
            f"official-infrastructure:{official_infrastructure_signature}"
        )
    errors.extend(official_retry_errors)

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
        "official_evaluation": {
            **official_provenance,
            "infrastructure_signature": official_infrastructure_signature,
        },
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
        "execution_identity": {
            "image_digest": image_digest,
            "goal_contract_sha256": goal_contract_sha256,
            "repository_integrity_valid": repository_integrity.get("valid"),
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
            "candidate_ready_to_replay": _candidate_ready_to_replay(events),
            "operation_constraint_violations": sum(
                item.get("operation_constraints_added") is not False for item in checks
            ),
            "ledger_metadata": ledger,
        },
    }


def _apply_cross_arm_validity(records: list[dict[str, Any]]) -> None:
    for pair_id in {item["pair_id"] for item in records}:
        pair = [item for item in records if item["pair_id"] == pair_id]
        for field, error in (
            ("image_digest", "cross-arm-image-digest-mismatch"),
            ("goal_contract_sha256", "cross-arm-goal-contract-hash-mismatch"),
        ):
            values = {
                item["execution_identity"].get(field)
                for item in pair
                if item["execution_identity"].get(field)
            }
            if len(pair) != 2 or len(values) != 1:
                for item in pair:
                    if error not in item["validity_errors"]:
                        item["validity_errors"].append(error)
                    item["censored"] = True


def _apply_replacement_schedules(
    episodes: list[dict[str, Any]],
    replacement_schedules: list[Path],
) -> list[dict[str, Any]]:
    replacements: dict[int, dict[str, Any]] = {}
    valid_positions = {int(item["position"]) for item in episodes}
    for path in replacement_schedules:
        replacement_episodes = read_json(path.resolve()).get("episodes")
        if not isinstance(replacement_episodes, list) or len(replacement_episodes) != 1:
            raise ValueError(
                f"Replacement schedule must contain exactly one episode: {path}"
            )
        replacement = replacement_episodes[0]
        if not isinstance(replacement, dict):
            raise ValueError(f"Replacement episode must be an object: {path}")
        original_position = replacement.get("original_position")
        if not isinstance(original_position, int):
            raise ValueError(
                f"Replacement episode must declare original_position: {path}"
            )
        if original_position not in valid_positions:
            raise ValueError(
                f"Replacement targets unknown position {original_position}: {path}"
            )
        if original_position in replacements:
            raise ValueError(f"Duplicate replacement for position {original_position}")
        replacements[original_position] = replacement
    return [replacements.get(int(item["position"]), item) for item in episodes]


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
    parser.add_argument(
        "--replacement-schedule",
        action="append",
        type=Path,
        required=True,
    )
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
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
