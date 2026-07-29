from __future__ import annotations

from collections import Counter, defaultdict
import json
from typing import Any

from envsolve.analysis.bootstrap_failures import observe_bootstrap_attempts
from envsolve.state import EnvironmentState


BOOTSTRAP_CONTRADICTION_FRONTIER_SCHEMA = (
    "envsolve-bootstrap-contradiction-frontier-v2"
)
MODEL_BOOTSTRAP_CONTRADICTION_FRONTIER_SCHEMA = (
    "envsolve-model-bootstrap-contradiction-frontier-v2"
)


def _branch_rows(
    attempts: tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        for runtime in attempt["runtime_branches"]:
            grouped[str(runtime)].append(attempt)

    rows: list[dict[str, Any]] = []
    for runtime, branch_attempts in sorted(grouped.items()):
        failed = [
            item for item in branch_attempts if item["outcome"] == "failed"
        ]
        succeeded = [
            item for item in branch_attempts if item["outcome"] == "succeeded"
        ]
        censored = [
            item
            for item in branch_attempts
            if item["outcome"] == "infrastructure-censored"
        ]
        strategy_count = len(
            {str(item["strategy_signature"]) for item in failed}
        )
        classified_failure_count = sum(
            item.get("failure", {}).get("failure_class")
            != "unclassified-bootstrap-failure"
            for item in failed
        )
        failure_counts = Counter(
            str(item["failure"]["signature"])
            for item in failed
            if isinstance(item.get("failure"), dict)
        )
        if succeeded:
            status = "bootstrap-observed-feasible"
        elif (
            len(failed) >= 3
            and strategy_count >= 2
            and classified_failure_count >= 2
        ):
            status = "search-dominated-by-observed-failures"
        elif failed:
            status = "observed-failed"
        else:
            status = "unobserved"
        rows.append(
            {
                "runtime_branch": runtime,
                "search_status": status,
                "failed_attempt_count": len(failed),
                "successful_bootstrap_count": len(succeeded),
                "infrastructure_censored_count": len(censored),
                "classified_failure_count": classified_failure_count,
                "distinct_failed_strategy_count": strategy_count,
                "repeated_failure_signature_count": sum(
                    count - 1
                    for count in failure_counts.values()
                    if count > 1
                ),
                "candidate_ids": [
                    str(item["candidate_id"]) for item in branch_attempts
                ],
                "failure_classes": dict(
                    sorted(
                        Counter(
                            str(item["failure"]["failure_class"])
                            for item in failed
                            if isinstance(item.get("failure"), dict)
                        ).items()
                    )
                ),
                "status_basis": (
                    "Observed bootstrap success overrides failure-only search "
                    "pressure."
                    if succeeded
                    else (
                        "At least three failed attempts span at least two "
                        "strategy signatures; this is search evidence, not a "
                        "proof of runtime infeasibility."
                        if status == "search-dominated-by-observed-failures"
                        else "Direct execution evidence only."
                    )
                ),
            }
        )
    return rows


def build_bootstrap_contradiction_frontier(
    state: EnvironmentState,
) -> dict[str, Any]:
    attempts = observe_bootstrap_attempts(state)
    failures = [
        item for item in attempts if item["outcome"] == "failed"
    ]
    successes = [
        item for item in attempts if item["outcome"] == "succeeded"
    ]
    censored = [
        item
        for item in attempts
        if item["outcome"] == "infrastructure-censored"
    ]
    failure_counts = Counter(
        str(item["failure"]["signature"])
        for item in failures
        if isinstance(item.get("failure"), dict)
    )
    repeated = [
        {
            "failure_signature": signature,
            "occurrence_count": count,
            "candidate_ids": [
                str(item["candidate_id"])
                for item in failures
                if item["failure"]["signature"] == signature
            ],
            "failure_class": next(
                str(item["failure"]["failure_class"])
                for item in failures
                if item["failure"]["signature"] == signature
            ),
            "subject": next(
                item["failure"].get("subject")
                for item in failures
                if item["failure"]["signature"] == signature
            ),
        }
        for signature, count in sorted(failure_counts.items())
        if count > 1
    ]
    branches = _branch_rows(attempts)
    return {
        "schema": BOOTSTRAP_CONTRADICTION_FRONTIER_SCHEMA,
        "raw_execution_feedback_retained": True,
        "hard_state_mutated": False,
        "inference_semantics": {
            "direct_attempt_outcomes_are_observations": True,
            "search_dominated_is_not_logical_infeasibility": True,
            "successful_bootstrap_overrides_failure_only_branch_status": True,
            "operation_space_closed": False,
        },
        "summary": {
            "observed_attempt_count": len(attempts),
            "failed_bootstrap_count": len(failures),
            "successful_bootstrap_count": len(successes),
            "infrastructure_censored_count": len(censored),
            "runtime_branch_count": len(branches),
            "search_dominated_branch_count": sum(
                item["search_status"]
                == "search-dominated-by-observed-failures"
                for item in branches
            ),
            "repeated_failure_signature_count": len(repeated),
        },
        "runtime_branches": branches,
        "repeated_failures": repeated,
        "attempts": list(attempts),
    }


def _encoded_chars(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=True, sort_keys=True))


def build_model_bootstrap_contradiction_frontier(
    state: EnvironmentState,
    *,
    max_chars: int = 10_000,
) -> dict[str, Any]:
    if max_chars < 2_000:
        raise ValueError(
            "Bootstrap contradiction frontier requires at least 2000 characters"
        )
    frontier = build_bootstrap_contradiction_frontier(state)
    projection = {
        **frontier,
        "schema": MODEL_BOOTSTRAP_CONTRADICTION_FRONTIER_SCHEMA,
        "source_schema": BOOTSTRAP_CONTRADICTION_FRONTIER_SCHEMA,
    }
    projection["summary"] = {
        **projection["summary"],
        "attempts_included": len(projection["attempts"]),
        "attempts_omitted": 0,
        "projection_complete": True,
    }
    if _encoded_chars(projection) <= max_chars:
        return projection

    for attempt in projection["attempts"]:
        failure = attempt.get("failure")
        if isinstance(failure, dict):
            failure.pop("excerpt", None)
    if _encoded_chars(projection) <= max_chars:
        return projection

    attempts = projection["attempts"]
    while attempts and _encoded_chars(projection) > max_chars:
        attempts.pop(0)
        projection["summary"]["attempts_included"] = len(attempts)
        projection["summary"]["attempts_omitted"] += 1
        projection["summary"]["projection_complete"] = False
    if _encoded_chars(projection) > max_chars:
        raise ValueError(
            "Bootstrap contradiction frontier exceeds its model context contract"
        )
    return projection
