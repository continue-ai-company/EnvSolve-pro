from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from envsolve_harness.audit import audit_run
from envsolve_harness.core.io import read_json, read_jsonl
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.utils.provenance import sha256_file


EMPTY_RESPONSE_SHA256 = (
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)
FORBIDDEN_REASONING_KEYS = {"reasoning", "reasoning_content", "reasoning_details"}


def _forbidden_reasoning_paths(value: Any, path: str = "$") -> list[str]:
    matches: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if key in FORBIDDEN_REASONING_KEYS:
                matches.append(child)
            matches.extend(_forbidden_reasoning_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            matches.extend(_forbidden_reasoning_paths(item, f"{path}[{index}]"))
    return matches


def summarize_output_contract_trajectory(
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    failures = [
        event for event in events if event.get("event_type") == "failure_recorded"
    ]
    failure_categories = Counter(
        str((event.get("payload") or {}).get("category")) for event in failures
    )
    policy_failures = [
        event
        for event in failures
        if str((event.get("payload") or {}).get("category", "")).startswith(
            "candidate-policy-"
        )
    ]
    empty_final_failures = sum(
        bool(((event.get("payload") or {}).get("details") or {}).get(
            "final_content_empty"
        ))
        or (((event.get("payload") or {}).get("details") or {}).get(
            "response_sha256"
        ))
        == EMPTY_RESPONSE_SHA256
        for event in policy_failures
    )
    length_finish_exceptions = sum(
        "LengthFinishReasonError" in str((event.get("payload") or {}).get("message"))
        for event in policy_failures
    )
    budget_as_policy_exception = sum(
        (event.get("payload") or {}).get("category")
        == "candidate-policy-exception"
        and "Online model budget exhausted:" in str(
            (event.get("payload") or {}).get("message")
        )
        for event in failures
    )
    return {
        "counts": {
            "proposals": sum(
                event.get("event_type") == "action_proposed" for event in events
            ),
            "verifications": sum(
                event.get("event_type") == "verification_recorded" for event in events
            ),
            "internal_passes": sum(
                event.get("event_type") == "verification_recorded"
                and (event.get("payload") or {}).get("passed") is True
                for event in events
            ),
            "policy_output_failures": failure_categories["candidate-policy-output"],
            "policy_exceptions": failure_categories["candidate-policy-exception"],
            "empty_final_failures": empty_final_failures,
            "length_finish_exceptions": length_finish_exceptions,
            "episode_budget_exhaustions": failure_categories[
                "episode-budget-exhausted"
            ],
            "provider_acquisition_failures": failure_categories[
                "provider-acquisition-failure"
            ],
            "budget_as_policy_exception": budget_as_policy_exception,
            "failure_categories": dict(sorted(failure_categories.items())),
        }
    }


def adjudicate_output_contract(
    counts: dict[str, Any],
    usage: dict[str, Any],
    persisted_reasoning_paths: list[str],
) -> dict[str, Any]:
    request_errors = int(usage.get("request_errors", 0))
    parse_retries = int(usage.get("response_parse_retries", 0))
    parse_recoveries = int(usage.get("response_parse_recoveries", 0))
    contradicted = bool(
        counts["empty_final_failures"]
        or counts["budget_as_policy_exception"]
        or persisted_reasoning_paths
    )
    practical_output_qualified = bool(
        int(usage.get("responses_completed", 0)) >= 5
        and counts["policy_output_failures"] == 0
        and counts["empty_final_failures"] == 0
        and request_errors == 0
    )
    provider_recovery_qualified = bool(
        int(usage.get("responses_completed", 0)) >= 5
        and request_errors > 0
        and request_errors == parse_retries
        and parse_recoveries > 0
        and counts["provider_acquisition_failures"] == 0
        and counts["policy_output_failures"] == 0
    )
    if contradicted:
        decision = "contradicted"
    elif practical_output_qualified:
        decision = "practical_output_qualified"
    elif provider_recovery_qualified:
        decision = "practical_output_qualified_with_provider_recovery"
    elif counts["length_finish_exceptions"]:
        decision = "unexercised_model_length_exception"
    elif request_errors or counts["provider_acquisition_failures"]:
        decision = (
            "inconclusive_provider_exception_after_practical_trigger"
            if int(counts["proposals"]) >= 5
            else "unexercised_provider_exception"
        )
    elif counts["internal_passes"]:
        decision = "unexercised_early_internal_pass"
    else:
        decision = "unexercised_boundary_not_reached"
    return {
        "contradicted": contradicted,
        "practical_output_qualified": practical_output_qualified,
        "provider_recovery_qualified": provider_recovery_qualified,
        "decision": decision,
    }


def analyze_output_contract_replay(
    schedule_path: Path,
    preregistration_path: Path,
    runs_root: Path,
) -> dict[str, Any]:
    schedule_path = schedule_path.resolve()
    preregistration_path = preregistration_path.resolve()
    preregistration = read_json(preregistration_path)
    preregistration_id = preregistration.get("preregistration_id")
    if not isinstance(preregistration_id, str) or not preregistration_id:
        raise ValueError("Output-contract preregistration requires an identifier")
    expected_schedule_sha256 = (preregistration.get("schedule") or {}).get("sha256")
    if sha256_file(schedule_path) != expected_schedule_sha256:
        raise ValueError("Schedule does not match output-contract preregistration")

    schedule = read_json(schedule_path)
    episodes = schedule.get("episodes")
    if not isinstance(episodes, list) or len(episodes) != 1:
        raise ValueError("Output-contract replay requires exactly one episode")
    episode = dict(episodes[0])
    root = (
        runs_root.resolve()
        / safe_name(str(episode["run_id"]))
        / safe_name(str(episode["case_id"]))
    )
    report = audit_run(root)
    if not report.valid:
        raise ValueError(f"Output-contract replay failed audit: {report.errors}")

    episode_path = root / "generation" / "episode.jsonl"
    ledger_path = root / "generation" / "budget_ledger.json"
    result_path = root / "generation" / "result.json"
    events = read_jsonl(episode_path)
    ledger = read_json(ledger_path)
    result = read_json(result_path)
    trajectory = summarize_output_contract_trajectory(events)
    counts = trajectory["counts"]
    usage = ledger.get("usage") or {}

    persisted_reasoning_paths: list[str] = []
    for name, value in (
        ("episode", events),
        ("ledger", ledger),
        ("result", result),
    ):
        persisted_reasoning_paths.extend(
            f"{name}:{path}" for path in _forbidden_reasoning_paths(value)
        )

    adjudication = adjudicate_output_contract(
        counts,
        usage,
        persisted_reasoning_paths,
    )

    return {
        "schema_version": "1.0.0",
        "analysis": preregistration_id,
        "claim_scope": "consumed-development mechanism replay only",
        "inputs": {
            "schedule": str(schedule_path),
            "schedule_sha256": sha256_file(schedule_path),
            "preregistration": str(preregistration_path),
            "preregistration_sha256": sha256_file(preregistration_path),
        },
        "run": {
            **{
                key: episode.get(key)
                for key in ("position", "case_id", "run_id", "method", "seed")
            },
            "artifact_root": str(root),
            "audit_valid": True,
            "generation_completed": bool(result.get("generation_completed")),
            "error": result.get("error"),
            "episode_sha256": sha256_file(episode_path),
            "ledger_sha256": sha256_file(ledger_path),
            "result_sha256": sha256_file(result_path),
            "official_evaluator_reached": (root / "evaluation" / "result.json").is_file(),
            "counts": counts,
            "usage": {
                key: usage.get(key)
                for key in (
                    "requests_started",
                    "responses_completed",
                    "request_errors",
                    "response_parse_retries",
                    "response_parse_recoveries",
                    "input_tokens",
                    "output_tokens",
                    "total_tokens",
                    "candidates",
                    "environments",
                    "commands",
                    "elapsed_wall_clock_seconds",
                )
            },
            "persisted_reasoning_paths": persisted_reasoning_paths,
        },
        "qualification": {
            "practical_output_qualified": adjudication[
                "practical_output_qualified"
            ],
            "provider_recovery_qualified": adjudication[
                "provider_recovery_qualified"
            ],
            "budget_terminal_qualified": (
                counts["budget_as_policy_exception"] == 0
                if counts["episode_budget_exhaustions"]
                else None
            ),
            "reasoning_content_absent": not persisted_reasoning_paths,
        },
        "decision": adjudication["decision"],
        "limitations": {
            "consumed_development_identity": True,
            "causal_effectiveness_estimate_allowed": False,
            "leaderboard_claim_allowed": False,
            "paper_test_set_claim_allowed": False,
        },
    }
