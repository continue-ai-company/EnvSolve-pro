from experiments.analyze_causal_frontier_pairs import aggregate, target_metrics


def test_target_metrics_requires_later_absence_for_closure() -> None:
    timeline = [
        {
            "phase": "decision",
            "after_candidate_index": 0,
            "target_present": False,
        },
        {
            "phase": "decision",
            "after_candidate_index": 1,
            "target_present": True,
        },
        {
            "phase": "decision",
            "after_candidate_index": 2,
            "target_present": True,
        },
        {
            "phase": "terminal",
            "after_candidate_index": 3,
            "target_present": False,
        },
    ]

    result = target_metrics(timeline)

    assert result == {
        "target_observed": True,
        "target_first_observed_after_candidate": 1,
        "target_recurrence_decisions": 2,
        "target_closed": True,
        "target_closed_by_candidate": 3,
    }


def _episode(
    pair: int,
    condition: str,
    *,
    success: bool,
    closed: bool,
) -> dict:
    return {
        "pair": pair,
        "condition": condition,
        "repository": f"owner/repo-{pair}",
        "official_pass": success,
        "measurement_integrity_ok": True,
        "target_metrics": {
            "target_observed": True,
            "target_first_observed_after_candidate": 1,
            "target_recurrence_decisions": 1,
            "target_closed": closed,
            "target_closed_by_candidate": 2 if closed else None,
        },
    }


def test_aggregate_applies_preregistered_proceed_rule() -> None:
    episodes = [
        _episode(1, "flat", success=False, closed=False),
        _episode(1, "causal-frontier", success=False, closed=True),
        _episode(2, "flat", success=True, closed=True),
        _episode(2, "causal-frontier", success=True, closed=True),
    ]

    result = aggregate(episodes)

    assert result["target_closures"] == {"flat": 1, "causal-frontier": 2}
    assert result["mechanism_improvement_observed"] is True
    assert result["no_paired_official_success_regression"] is True
    assert result["preregistered_proceed_rule_satisfied"] is True
