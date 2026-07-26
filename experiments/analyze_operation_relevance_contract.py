#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any


# ruff: noqa: E402 - workspace path bootstrapping must precede local imports.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.runtime.operation_contract import OperationRelevanceContract
from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.results import summarize_schedule
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.utils.provenance import sha256_file


TREATMENT = "operation-contract-v1"
CONTROL = "frozen-fresh-control"
TERMINAL_CLASSES = {
    "official_pass",
    "official_fail",
    "provider_infrastructure_unknown",
    "provider_response_unknown",
    "infrastructure_unknown",
    "execution_timeout_unknown",
    "evaluator_unknown",
    "measurement_integrity_unknown",
    "budget_exhausted",
    "candidate_limit",
    "context_contract_exhausted",
    "generation_failed",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the operation-relevance contract qualification."
    )
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _candidate_id(event: dict[str, Any]) -> str | None:
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return None
    if event.get("event_type") == "action_proposed":
        value = payload.get("action_id")
    else:
        details = payload.get("details")
        value = (
            details.get("candidate_id")
            if isinstance(details, dict)
            else None
        )
    return value if isinstance(value, str) and value else None


def _goal_report(event: dict[str, Any]) -> dict[str, Any] | None:
    payload = event.get("payload")
    details = payload.get("details") if isinstance(payload, dict) else None
    verifier = (
        details.get("verifier_details")
        if isinstance(details, dict)
        else None
    )
    report_details = (
        verifier.get("report_details")
        if isinstance(verifier, dict)
        else None
    )
    report = (
        report_details.get("goal_report")
        if isinstance(report_details, dict)
        else None
    )
    return report if isinstance(report, dict) else None


def _progress_status(
    contract: OperationRelevanceContract,
    verification: dict[str, Any] | None,
) -> str:
    if verification is None:
        return "unknown"
    payload = verification.get("payload")
    if not isinstance(payload, dict):
        return "unknown"
    if payload.get("passed") is True:
        return "met"
    report = _goal_report(verification)
    if report is None or report.get("finding_set_complete") is not True:
        return "unknown"
    active = {
        str(finding["finding_id"])
        for finding in report.get("findings", [])
        if isinstance(finding, dict)
        and isinstance(finding.get("finding_id"), str)
        and finding.get("observed") is not None
        and finding.get("observed") != finding.get("required")
    }
    expected = set(contract.expected_resolved_finding_ids)
    still_active = (expected & active) | {
        item for item in expected if item.startswith("goal:")
    }
    return "not_met" if still_active else "met"


def mechanism_metrics(
    events: list[dict[str, Any]],
    *,
    treatment: bool,
) -> dict[str, Any]:
    proposals = [
        event
        for event in events
        if event.get("event_type") == "action_proposed"
    ]
    verification_by_candidate = {
        candidate_id: event
        for event in events
        if event.get("event_type") == "verification_recorded"
        and (candidate_id := _candidate_id(event)) is not None
    }
    errors: list[str] = []
    progress = Counter()
    contracts = 0
    family_ids: list[str] = []
    for event in proposals:
        payload = event.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        metadata = payload.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        raw_contract = metadata.get("operation_contract")
        if not treatment:
            if raw_contract is not None:
                errors.append("control candidate carries an operation contract")
            continue
        candidate_id = str(payload.get("action_id"))
        try:
            contract = OperationRelevanceContract.from_dict(raw_contract)
        except ValueError as exc:
            errors.append(f"{candidate_id}: invalid operation contract: {exc}")
            continue
        contracts += 1
        family_ids.append(contract.operation_family.family_id)
        projection = metadata.get("model_input_projection")
        projection = projection if isinstance(projection, dict) else {}
        context = projection.get("operation_context")
        if not isinstance(context, dict):
            errors.append(f"{candidate_id}: operation context is absent")
            progress["unknown"] += 1
            continue
        active_targets = {
            str(item["finding_id"])
            for item in context.get("active_targets", [])
            if isinstance(item, dict)
            and isinstance(item.get("finding_id"), str)
        }
        available_evidence = {
            str(item["evidence_id"])
            for item in context.get("available_precondition_evidence", [])
            if isinstance(item, dict)
            and isinstance(item.get("evidence_id"), str)
        }
        unknown_targets = set(contract.target_finding_ids) - active_targets
        unknown_evidence = (
            set(contract.precondition_evidence_ids) - available_evidence
        )
        if unknown_targets:
            errors.append(
                f"{candidate_id}: target IDs absent from model input"
            )
        if unknown_evidence:
            errors.append(
                f"{candidate_id}: evidence IDs absent from model input"
            )
        progress[
            _progress_status(
                contract,
                verification_by_candidate.get(candidate_id),
            )
        ] += 1

    policy_rejections = Counter()
    for event in events:
        if event.get("event_type") != "failure_recorded":
            continue
        payload = event.get("payload")
        if (
            not isinstance(payload, dict)
            or payload.get("category")
            != "candidate-policy-operation-contract"
        ):
            continue
        details = payload.get("details")
        reason = (
            details.get("reason_code")
            if isinstance(details, dict)
            else None
        )
        policy_rejections[
            str(reason or "invalid-or-unparseable-contract")
        ] += 1

    candidate_verifications = [
        event
        for event in events
        if event.get("event_type") == "verification_recorded"
        and _candidate_id(event) is not None
    ]
    first_failure_index = next(
        (
            index
            for index, event in enumerate(candidate_verifications)
            if isinstance(event.get("payload"), dict)
            and event["payload"].get("passed") is False
        ),
        None,
    )
    later_internal_pass = (
        first_failure_index is not None
        and any(
            isinstance(event.get("payload"), dict)
            and event["payload"].get("passed") is True
            for event in candidate_verifications[first_failure_index + 1 :]
        )
    )
    suppression_reasons = {
        "repeated-failed-script",
        "repeated-family-without-new-evidence",
    }
    return {
        "valid": not errors,
        "errors": errors,
        "candidate_proposals": len(proposals),
        "executed_candidates": sum(
            event.get("event_type") == "action_finished"
            for event in events
        ),
        "operation_contracts": contracts,
        "distinct_operation_families": len(set(family_ids)),
        "policy_rejections_by_reason": dict(sorted(policy_rejections.items())),
        "suppression_events": sum(
            policy_rejections[reason] for reason in suppression_reasons
        ),
        "progress_calibration": {
            key: progress[key] for key in ("met", "not_met", "unknown")
        },
        "first_internal_goal_failure_observed": (
            first_failure_index is not None
        ),
        "later_internal_goal_pass_observed": later_internal_pass,
    }


def _aggregate_condition(
    runs: list[dict[str, Any]],
    condition: str,
) -> dict[str, Any]:
    selected = [run for run in runs if run["condition"] == condition]
    rejection_counts: Counter[str] = Counter()
    progress_counts: Counter[str] = Counter()
    for run in selected:
        mechanism = run["mechanism"]
        rejection_counts.update(mechanism["policy_rejections_by_reason"])
        progress_counts.update(mechanism["progress_calibration"])
    return {
        "runs": len(selected),
        "scientifically_eligible": sum(
            bool(run["scientifically_eligible"]) for run in selected
        ),
        "official_pass": sum(
            run["official_pass"] is True for run in selected
        ),
        "official_fail": sum(
            run["official_pass"] is False for run in selected
        ),
        "official_unknown": sum(
            run["official_pass"] is None for run in selected
        ),
        "candidate_proposals": sum(
            run["mechanism"]["candidate_proposals"] for run in selected
        ),
        "executed_candidates": sum(
            run["mechanism"]["executed_candidates"] for run in selected
        ),
        "operation_contracts": sum(
            run["mechanism"]["operation_contracts"] for run in selected
        ),
        "policy_rejections_by_reason": dict(sorted(rejection_counts.items())),
        "suppression_events": sum(
            run["mechanism"]["suppression_events"] for run in selected
        ),
        "progress_calibration": {
            key: progress_counts[key]
            for key in ("met", "not_met", "unknown")
        },
        "post_first_failure_internal_repairs": sum(
            run["mechanism"]["later_internal_goal_pass_observed"]
            for run in selected
        ),
        "post_first_failure_official_repairs": sum(
            run["mechanism"]["first_internal_goal_failure_observed"]
            and run["official_pass"] is True
            for run in selected
        ),
    }


def paired_metrics(runs: list[dict[str, Any]]) -> dict[str, int]:
    blocks: dict[int, dict[str, dict[str, Any]]] = {}
    for run in runs:
        blocks.setdefault(int(run["case_block"]), {})[
            str(run["condition"])
        ] = run
    counts = {
        "case_blocks": len(blocks),
        "eligible_blocks": 0,
        "censored_blocks": 0,
        "treatment_only_pass": 0,
        "control_only_pass": 0,
        "both_pass": 0,
        "neither_pass": 0,
        "treatment_only_official_repair": 0,
    }
    for conditions in blocks.values():
        if set(conditions) != {TREATMENT, CONTROL}:
            counts["censored_blocks"] += 1
            continue
        treatment = conditions[TREATMENT]
        control = conditions[CONTROL]
        eligible = (
            treatment["scientifically_eligible"]
            and control["scientifically_eligible"]
            and isinstance(treatment["official_pass"], bool)
            and isinstance(control["official_pass"], bool)
        )
        if not eligible:
            counts["censored_blocks"] += 1
            continue
        counts["eligible_blocks"] += 1
        outcomes = (treatment["official_pass"], control["official_pass"])
        if outcomes == (True, True):
            counts["both_pass"] += 1
        elif outcomes == (True, False):
            counts["treatment_only_pass"] += 1
            if treatment["mechanism"][
                "first_internal_goal_failure_observed"
            ]:
                counts["treatment_only_official_repair"] += 1
        elif outcomes == (False, True):
            counts["control_only_pass"] += 1
        else:
            counts["neither_pass"] += 1
    return counts


def analyze(schedule_path: Path, runs_root: Path) -> dict[str, Any]:
    schedule_path = schedule_path.resolve()
    runs_root = runs_root.resolve()
    schedule = read_json(schedule_path)
    episodes = schedule.get("episodes")
    if not isinstance(episodes, list):
        raise ValueError("Schedule must contain episodes")
    base = summarize_schedule(schedule_path, runs_root)
    base_by_run = {str(run["run_id"]): run for run in base["runs"]}
    runs = []
    for episode in episodes:
        run_id = str(episode["run_id"])
        case_id = str(episode["case_id"])
        root = runs_root / safe_name(run_id) / safe_name(case_id)
        trajectory = root / "generation" / "episode.jsonl"
        condition = str(episode["condition"])
        base_run = base_by_run[run_id]
        runs.append(
            {
                **base_run,
                "case_block": int(episode["case_block"]),
                "condition": condition,
                "trajectory_sha256": (
                    sha256_file(trajectory) if trajectory.is_file() else None
                ),
                "mechanism": mechanism_metrics(
                    _read_jsonl(trajectory),
                    treatment=condition == TREATMENT,
                ),
            }
        )

    by_condition = {
        condition: _aggregate_condition(runs, condition)
        for condition in (CONTROL, TREATMENT)
    }
    paired = paired_metrics(runs)
    schedule_complete = all(
        run["descriptive_terminal"] in TERMINAL_CLASSES for run in runs
    )
    mechanism_integrity = all(
        run["mechanism"]["valid"] for run in runs
    )
    all_pairs_eligible = paired["eligible_blocks"] == paired["case_blocks"]
    no_official_regression = (
        all_pairs_eligible
        and by_condition[TREATMENT]["official_pass"]
        >= by_condition[CONTROL]["official_pass"]
    )
    suppression_observed = (
        by_condition[TREATMENT]["suppression_events"] > 0
    )
    treatment_only_repair = paired["treatment_only_official_repair"] > 0
    if not schedule_complete:
        decision = "incomplete"
    elif not mechanism_integrity:
        decision = "invalid-mechanism-integrity"
    elif not all_pairs_eligible:
        decision = "censored-needs-infrastructure-closure"
    elif not no_official_regression:
        decision = "archive-v1-official-regression"
    elif treatment_only_repair:
        decision = "retain-v1-treatment-only-official-repair"
    elif suppression_observed:
        decision = "manual-review-suppression-calibration"
    else:
        decision = "archive-v1-no-preregistered-mechanism-signal"
    return {
        "schema_version": "1.0.0",
        "study_id": schedule.get("study_id"),
        "schedule": {
            "path": str(schedule_path),
            "sha256": sha256_file(schedule_path),
        },
        "claim_scope": (
            "Repository-disjoint development qualification; not final test "
            "or leaderboard evidence."
        ),
        "by_condition": by_condition,
        "paired": paired,
        "gate": {
            "schedule_complete": schedule_complete,
            "mechanism_integrity_valid": mechanism_integrity,
            "all_pairs_scientifically_eligible": all_pairs_eligible,
            "no_official_pass_regression": no_official_regression,
            "treatment_only_official_repair_observed": treatment_only_repair,
            "suppression_observed": suppression_observed,
            "suppression_correctness": (
                "requires blinded trajectory review"
                if suppression_observed
                else "not_applicable"
            ),
            "decision": decision,
        },
        "runs": runs,
    }


def main() -> int:
    args = parse_args()
    result = analyze(args.schedule, args.runs_root)
    write_json(args.output, result)
    print(f"output={args.output.resolve()}")
    print(
        f"complete={result['gate']['schedule_complete']} "
        f"integrity={result['gate']['mechanism_integrity_valid']} "
        f"decision={result['gate']['decision']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
