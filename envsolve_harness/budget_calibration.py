from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from envsolve_harness.audit import audit_run
from envsolve_harness.core.io import read_json, read_jsonl
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.utils.provenance import sha256_file


PRE_ENVIRONMENT_REJECT_CODES = {251, 252}
EMPTY_RESPONSE_SHA256 = (
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)


def summarize_budget_trajectory(
    events: list[dict[str, Any]],
    old_candidate_cap: int,
) -> dict[str, Any]:
    proposed = sorted(
        (event for event in events if event.get("event_type") == "action_proposed"),
        key=lambda event: int(event["sequence"]),
    )
    finished = {
        str((event.get("payload") or {}).get("action_id")): event
        for event in events
        if event.get("event_type") == "action_finished"
    }
    candidates: list[dict[str, Any]] = []
    for proposal_index, event in enumerate(proposed, start=1):
        candidate_id = str((event.get("payload") or {}).get("action_id"))
        finished_event = finished.get(candidate_id)
        if finished_event is None:
            raise ValueError(f"Candidate has no finished transition: {candidate_id}")
        exit_code = (finished_event.get("payload") or {}).get("exit_code")
        executed = exit_code not in PRE_ENVIRONMENT_REJECT_CODES
        candidates.append(
            {
                "candidate_id": candidate_id,
                "proposal_index": proposal_index,
                "exit_code": exit_code,
                "executed": executed,
                "after_old_candidate_cap": proposal_index > old_candidate_cap,
            }
        )

    verifications = [
        event for event in events if event.get("event_type") == "verification_recorded"
    ]
    failures = [
        event for event in events if event.get("event_type") == "failure_recorded"
    ]
    failure_categories = Counter(
        str((event.get("payload") or {}).get("category")) for event in failures
    )
    policy_exception_messages = [
        str((event.get("payload") or {}).get("message") or "")
        for event in failures
        if (event.get("payload") or {}).get("category")
        == "candidate-policy-exception"
    ]
    budget_preflight_exceptions = sum(
        message.startswith("BudgetExceeded: Online model budget exhausted:")
        for message in policy_exception_messages
    )
    empty_policy_responses = sum(
        (event.get("payload") or {}).get("category") == "candidate-policy-output"
        and (((event.get("payload") or {}).get("details") or {}).get("response_sha256"))
        == EMPTY_RESPONSE_SHA256
        for event in failures
    )
    return {
        "candidates": candidates,
        "counts": {
            "proposals": len(candidates),
            "executed": sum(bool(item["executed"]) for item in candidates),
            "pre_environment_rejects": sum(
                not bool(item["executed"]) for item in candidates
            ),
            "proposals_after_old_cap": sum(
                bool(item["after_old_candidate_cap"]) for item in candidates
            ),
            "executions_after_old_cap": sum(
                bool(item["executed"]) and bool(item["after_old_candidate_cap"])
                for item in candidates
            ),
            "internal_passes": sum(
                (event.get("payload") or {}).get("passed") is True
                for event in verifications
            ),
            "policy_output_failures": failure_categories["candidate-policy-output"],
            "empty_policy_responses": empty_policy_responses,
            "policy_exceptions": failure_categories["candidate-policy-exception"],
            "budget_preflight_exceptions": budget_preflight_exceptions,
            "unexpected_policy_exceptions": (
                failure_categories["candidate-policy-exception"]
                - budget_preflight_exceptions
            ),
            "failure_categories": dict(sorted(failure_categories.items())),
        },
    }


def _run_root(episode: dict[str, Any], runs_root: Path) -> Path:
    return (
        runs_root
        / safe_name(str(episode["run_id"]))
        / safe_name(str(episode["case_id"]))
    ).resolve()


def _analyze_run(
    episode: dict[str, Any],
    runs_root: Path,
    old_candidate_cap: int,
) -> dict[str, Any]:
    root = _run_root(episode, runs_root)
    report = audit_run(root)
    if not report.valid:
        raise ValueError(f"Budget calibration run failed audit: {root}: {report.errors}")
    episode_path = root / "generation" / "episode.jsonl"
    ledger_path = root / "generation" / "budget_ledger.json"
    result_path = root / "generation" / "result.json"
    trajectory = summarize_budget_trajectory(
        read_jsonl(episode_path), old_candidate_cap
    )
    ledger = read_json(ledger_path)
    result = read_json(result_path)
    usage = ledger.get("usage") or {}
    counts = trajectory["counts"]
    if int(usage.get("candidates", -1)) != int(counts["proposals"]):
        raise ValueError(f"Candidate ledger mismatch: {root}")
    if int(usage.get("environments", -1)) != int(counts["executed"]):
        raise ValueError(f"Environment ledger mismatch: {root}")
    if int(usage.get("commands", -1)) != int(counts["executed"]):
        raise ValueError(f"Command ledger mismatch: {root}")

    metadata = result.get("metadata") or {}
    episode_result = metadata.get("episode") or {}
    return {
        **{
            key: episode.get(key)
            for key in ("position", "pair_index", "case_id", "run_id", "method", "seed")
        },
        "audit_valid": True,
        "episode_sha256": sha256_file(episode_path),
        "ledger_sha256": sha256_file(ledger_path),
        "result_sha256": sha256_file(result_path),
        "generation_completed": bool(result.get("generation_completed")),
        "terminal_reason": result.get("error") or episode_result.get("stop_reason"),
        "goal_status": episode_result.get("goal_status"),
        "official_evaluator_reached": (root / "evaluation" / "result.json").is_file(),
        "counts": counts,
        "usage": {
            key: usage.get(key)
            for key in (
                "requests_started",
                "responses_completed",
                "request_errors",
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "candidates",
                "environments",
                "commands",
                "elapsed_wall_clock_seconds",
            )
        },
        "exhausted_limits": ledger.get("exhausted_limits") or [],
        "termination": ledger.get("termination"),
        "candidates": trajectory["candidates"],
    }


def _aggregate(
    runs: list[dict[str, Any]], old_candidate_cap: int
) -> dict[str, Any]:
    resources = Counter()
    terminal_reasons: Counter[str] = Counter()
    failure_categories: Counter[str] = Counter()
    count_keys = (
        "proposals",
        "executed",
        "pre_environment_rejects",
        "proposals_after_old_cap",
        "executions_after_old_cap",
        "internal_passes",
        "policy_output_failures",
        "empty_policy_responses",
        "policy_exceptions",
        "budget_preflight_exceptions",
        "unexpected_policy_exceptions",
    )
    counts = Counter()
    resource_keys = (
        "requests_started",
        "responses_completed",
        "request_errors",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "candidates",
        "environments",
        "commands",
        "elapsed_wall_clock_seconds",
    )
    for run in runs:
        counts.update({key: run["counts"][key] for key in count_keys})
        failure_categories.update(run["counts"]["failure_categories"])
        resources.update(
            {key: run["usage"].get(key) or 0 for key in resource_keys}
        )
        terminal_reasons[str(run.get("terminal_reason"))] += 1
    return {
        "runs": len(runs),
        "audit_valid": sum(bool(run["audit_valid"]) for run in runs),
        "generation_completed": sum(bool(run["generation_completed"]) for run in runs),
        "official_evaluator_reached": sum(
            bool(run["official_evaluator_reached"]) for run in runs
        ),
        "runs_over_old_candidate_cap": sum(
            int(run["counts"]["proposals"]) > old_candidate_cap for run in runs
        ),
        "runs_with_executions_after_old_cap": sum(
            int(run["counts"]["executions_after_old_cap"]) > 0 for run in runs
        ),
        **dict(counts),
        "failure_categories": dict(sorted(failure_categories.items())),
        "terminal_reasons": dict(sorted(terminal_reasons.items())),
        "resources": dict(resources),
    }


def analyze_budget_calibration(
    schedule_path: Path,
    preregistration_path: Path,
    runs_root: Path,
    historical_closure_path: Path,
) -> dict[str, Any]:
    schedule_path = schedule_path.resolve()
    preregistration_path = preregistration_path.resolve()
    historical_closure_path = historical_closure_path.resolve()
    preregistration = read_json(preregistration_path)
    expected_schedule_sha256 = (preregistration.get("schedule") or {}).get("sha256")
    if sha256_file(schedule_path) != expected_schedule_sha256:
        raise ValueError("Schedule does not match budget calibration preregistration")
    source = preregistration.get("source_evidence") or {}
    if sha256_file(historical_closure_path) != source.get("q10_closure_sha256"):
        raise ValueError("Historical Q10 closure does not match preregistration")
    old_candidate_cap = int(
        ((preregistration.get("budget_intervention") or {}).get("old") or {})[
            "max_candidates"
        ]
    )
    schedule = read_json(schedule_path)
    episodes = schedule.get("episodes")
    if not isinstance(episodes, list):
        raise ValueError("Schedule must contain an episode list")
    runs = [
        _analyze_run(dict(episode), runs_root.resolve(), old_candidate_cap)
        for episode in sorted(episodes, key=lambda item: int(item["position"]))
    ]
    aggregate = _aggregate(runs, old_candidate_cap)
    methods = {
        method: _aggregate(
            [run for run in runs if run.get("method") == method],
            old_candidate_cap,
        )
        for method in sorted({str(run.get("method")) for run in runs})
    }
    if aggregate["internal_passes"] or aggregate["official_evaluator_reached"]:
        decision = "terminal_reach_after_proposal_five"
    elif aggregate["executions_after_old_cap"]:
        decision = "additional_environments_without_terminal_reach"
    else:
        decision = "no_additional_proposals"
    historical = read_json(historical_closure_path)
    return {
        "schema_version": "1.0.0",
        "claim_scope": "consumed-development budget calibration only",
        "schedule": {"path": schedule_path.name, "sha256": sha256_file(schedule_path)},
        "preregistration": {
            "path": preregistration_path.name,
            "sha256": sha256_file(preregistration_path),
        },
        "historical_q10": {
            "path": historical_closure_path.name,
            "sha256": sha256_file(historical_closure_path),
            "resources": (historical.get("resources") or {}).get("combined"),
            "descriptive_only": True,
        },
        "old_candidate_cap": old_candidate_cap,
        "decision": decision,
        "aggregate": aggregate,
        "methods": methods,
        "runs": runs,
    }
