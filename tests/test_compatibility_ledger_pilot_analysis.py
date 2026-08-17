from __future__ import annotations

from experiments.analyze_compatibility_ledger_pilot import (
    _adjudicate,
    _candidate_event,
    _pairs,
    _terminal_provider_failure,
    _usage,
)


def test_candidate_boundary_requires_a_hash_matched_certificate() -> None:
    events = [
        {
            "event": "tool_result",
            "tool_name": "submit_and_replay",
            "request_index": 2,
            "result": {
                "status": "pass",
                "program_sha256": "candidate",
                "certificate": {"program_sha256": "different"},
            },
        },
        {
            "event": "tool_result",
            "tool_name": "submit_and_replay",
            "request_index": 4,
            "result": {
                "status": "pass",
                "program_sha256": "candidate",
                "certificate": {"program_sha256": "candidate"},
            },
        },
    ]

    assert _candidate_event(events) is events[1]


def test_usage_stops_at_the_frozen_candidate_boundary() -> None:
    events = [
        {
            "event": "provider_response",
            "request_index": index,
            "response": {
                "usage": {
                    "prompt_tokens": 10 * index,
                    "completion_tokens": index,
                    "total_tokens": 11 * index,
                    "cost": 0.1 * index,
                    "completion_tokens_details": {"reasoning_tokens": index - 1},
                }
            },
        }
        for index in (1, 2, 3)
    ]

    assert _usage(events, 2) == {
        "model_requests": 2,
        "prompt_tokens": 30,
        "completion_tokens": 3,
        "reasoning_tokens": 1,
        "total_tokens": 33,
        "cost": 0.30000000000000004,
    }


def test_terminal_provider_failure_requires_no_later_success() -> None:
    failure = {
        "event": "provider_error",
        "request_index": 3,
        "next_retry_delay_seconds": None,
    }
    assert _terminal_provider_failure([failure]) is True
    assert (
        _terminal_provider_failure(
            [failure, {"event": "provider_response", "request_index": 3}]
        )
        is False
    )


def _record(pair: int, arm: str) -> dict[str, object]:
    treatment = arm == "D-LEDGER"
    value = 8 if treatment else 10
    return {
        "pair_id": f"pair-{pair}",
        "arm": arm,
        "censored": False,
        "candidate_formed": True,
        "official_pass": True,
        "pre_candidate": {
            "model_requests": value,
            "interactive_tool_steps": value,
            "total_tokens": value * 100,
            "seconds_to_certificate": value * 10,
        },
        "mechanism": {
            "check_count": 1 if treatment else 0,
            "complete_check_count": 1 if treatment else 0,
            "operation_constraint_violations": 0,
            "ledger_metadata": (
                {
                    "transition_counts": {"initial": 1, "improved": 1},
                    "stores_container_checkpoint": False,
                }
                if treatment
                else {}
            ),
        },
    }


def test_adjudication_applies_the_preregistered_efficiency_rule() -> None:
    records = [
        _record(pair, arm)
        for pair in range(4)
        for arm in ("B-FSR", "D-LEDGER")
    ]
    pairs = _pairs(records)  # type: ignore[arg-type]
    result = _adjudicate(records, pairs)  # type: ignore[arg-type]

    assert result["mechanism_acceptance"]["passed"] is True
    assert result["directional"]["efficiency_signal"] is True
    assert result["decision"] == (
        "positive-directional-promote-to-broader-consumed-study"
    )


def test_adjudication_rejects_lower_treatment_success_count() -> None:
    records = [
        _record(pair, arm)
        for pair in range(4)
        for arm in ("B-FSR", "D-LEDGER")
    ]
    treatment = next(
        item
        for item in records
        if item["pair_id"] == "pair-0" and item["arm"] == "D-LEDGER"
    )
    treatment["candidate_formed"] = False
    treatment["official_pass"] = False
    pairs = _pairs(records)  # type: ignore[arg-type]
    result = _adjudicate(records, pairs)  # type: ignore[arg-type]

    assert result["decision"] == "negative-directional-do-not-expose-frozen-dev"
