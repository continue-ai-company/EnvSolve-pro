from envsolve.state.events import EventType, StateEvent
from experiments.analyze_causal_frontier_v3_pairs import aggregate, classify_terminal


def _event(event_type: EventType, payload: dict, sequence: int = 0) -> StateEvent:
    required = {
        "verification_id": "verification-1",
        "level": "internal",
        "verifier": "test",
        "passed": None,
        "details": {},
    }
    required.update(payload)
    return StateEvent.create(
        case_id="case",
        sequence=sequence,
        timestamp="2026-07-23T00:00:00+00:00",
        event_type=event_type,
        payload=required,
        previous_hash="0" * 64,
    )


def test_candidate_budget_terminal_is_an_algorithmic_failure() -> None:
    result = classify_terminal(
        {"generation_completed": False, "error": "candidate budget exhausted"},
        {},
        {"exhausted_limits": ["candidates", "environments", "commands"]},
        [],
    )

    assert result["class"] == "algorithmic_no_candidate"
    assert result["success"] is False


def test_infrastructure_observation_censors_candidate_budget_terminal() -> None:
    event = _event(
        EventType.VERIFICATION_RECORDED,
        {
            "details": {
                "verifier_details": {
                    "infrastructure_error": "dependency_acquisition_failure",
                    "infrastructure_signature": "read-timeout",
                }
            }
        },
    )

    result = classify_terminal(
        {"generation_completed": False, "error": "candidate budget exhausted"},
        {},
        {"exhausted_limits": ["candidates"]},
        [event],
    )

    assert result["class"] == "infrastructure_censored"
    assert result["success"] is None


def test_identity_matched_official_outcome_is_scorable() -> None:
    result = classify_terminal(
        {"generation_completed": True},
        {
            "evaluation_completed": True,
            "official_pass": False,
            "metadata": {"identity_matches": True},
        },
        {},
        [],
    )

    assert result["class"] == "official_fail"
    assert result["success"] is False


def _episode(pair: int, condition: str, success: bool, closed: bool) -> dict:
    return {
        "pair": pair,
        "block": 1,
        "condition": condition,
        "projection_integrity_ok": True,
        "repository": f"owner/repo-{pair}",
        "terminal": {"success": success},
        "target_metrics": {
            "target_observed": True,
            "target_closed": closed,
        },
    }


def test_aggregate_reports_paired_success_and_comparable_closure() -> None:
    result = aggregate(
        [
            _episode(1, "flat", False, False),
            _episode(1, "causal-frontier", True, True),
            _episode(2, "flat", True, True),
            _episode(2, "causal-frontier", True, True),
        ]
    )

    assert result["eligible_pair_count"] == 2
    assert result["official_passes"] == {"flat": 1, "causal-frontier": 2}
    assert result["official_success_delta_sum"] == 1
    assert result["target_closure_delta_sum"] == 1
