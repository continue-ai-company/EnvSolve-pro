from __future__ import annotations

from experiments.analyze_trajectory_census import (
    aggregate,
    best_complete_candidate,
    classify_case,
    select_case_attempt,
)


def candidate(
    index: int,
    *,
    exit_code: int = 0,
    completed: bool = True,
    effect_valid: bool = True,
    unknown: int = 0,
    unresolved: int = 0,
    satisfied: int = 1,
    infrastructure_signature: str | None = None,
) -> dict[str, object]:
    return {
        "candidate_id": f"candidate-{index:04d}",
        "candidate_index": index,
        "bootstrap_exit_code": exit_code,
        "completed": completed,
        "effect_valid": effect_valid,
        "infrastructure_error": (
            "dependency_acquisition_failure" if infrastructure_signature else None
        ),
        "infrastructure_signature": infrastructure_signature,
        "reported_passed": unresolved == 0 and unknown == 0 and exit_code == 0,
        "admissible": exit_code == 0 and completed and effect_valid and unknown == 0,
        "satisfied_constraints": satisfied,
        "unknown_constraints": unknown,
        "unresolved_constraints": unresolved,
    }


def generation(certification: str | None = None) -> dict[str, object]:
    return {
        "metadata": {"episode": {"candidate_certification": certification}},
    }


def test_classification_follows_preregistered_layer_order() -> None:
    assert classify_case(
        generation=generation("certified"),
        evaluation={"official_pass": True, "evaluation_completed": True},
        candidates=[],
    )[0] == "success"
    assert classify_case(
        generation=generation("certified"),
        evaluation={"official_pass": False, "evaluation_completed": True},
        candidates=[candidate(1)],
    )[0] == "evaluator_gap"
    assert classify_case(
        generation=generation(),
        evaluation=None,
        candidates=[candidate(1, unknown=2, unresolved=3)],
    )[0] == "observability_gap"
    assert classify_case(
        generation=generation(),
        evaluation=None,
        candidates=[candidate(1, unresolved=3)],
    )[0] == "closure_gap"
    assert classify_case(
        generation=generation(),
        evaluation=None,
        candidates=[candidate(1, exit_code=1, completed=False, effect_valid=False)],
    )[0] == "operation_nonviability"


def test_infrastructure_failure_is_censored_before_failure_classification() -> None:
    category, reason = classify_case(
        generation={"error": "Candidate execution was blocked by infrastructure failure"},
        evaluation=None,
        candidates=[
            candidate(
                1,
                exit_code=2,
                completed=False,
                effect_valid=False,
                infrastructure_signature="read-timeout",
            )
        ],
    )
    assert category is None
    assert "read-timeout" in reason


def test_case_attempt_selection_only_replaces_infrastructure_censoring() -> None:
    infrastructure = {
        "scientifically_complete": False,
        "infrastructure_censored": True,
        "artifact_root": "source",
    }
    replacement = {
        "scientifically_complete": True,
        "infrastructure_censored": False,
        "artifact_root": "replacement",
    }
    ordinary_failure = {
        "scientifically_complete": True,
        "infrastructure_censored": False,
        "artifact_root": "ordinary",
    }
    assert select_case_attempt([infrastructure, replacement]) is replacement
    assert select_case_attempt([ordinary_failure, replacement]) is ordinary_failure


def test_best_candidate_prefers_observed_closure_then_residual_count() -> None:
    best = best_complete_candidate(
        [
            candidate(1, unknown=1, unresolved=0, satisfied=20),
            candidate(2, unknown=0, unresolved=4, satisfied=10),
            candidate(3, unknown=0, unresolved=2, satisfied=8),
            candidate(4, unknown=0, unresolved=2, satisfied=12),
        ]
    )
    assert best is not None
    assert best["candidate_id"] == "candidate-0004"


def test_aggregate_requires_complete_unique_leader() -> None:
    cases = [
        {
            "scientifically_complete": True,
            "category": "closure_gap",
            "infrastructure_censored": False,
            "candidate_statistics": {
                "verified_candidates": 2,
                "execution_timeouts": 0,
                "effect_audit_failures": 0,
                "complete_zero_exit_effect_valid": 1,
                "internally_reported_passed": 0,
            },
        },
        {
            "scientifically_complete": True,
            "category": "closure_gap",
            "infrastructure_censored": False,
            "candidate_statistics": {
                "verified_candidates": 1,
                "execution_timeouts": 0,
                "effect_audit_failures": 0,
                "complete_zero_exit_effect_valid": 1,
                "internally_reported_passed": 0,
            },
        },
        {
            "scientifically_complete": True,
            "category": "operation_nonviability",
            "infrastructure_censored": False,
            "candidate_statistics": {
                "verified_candidates": 3,
                "execution_timeouts": 1,
                "effect_audit_failures": 0,
                "complete_zero_exit_effect_valid": 0,
                "internally_reported_passed": 0,
            },
        },
    ]
    summary = aggregate(cases)
    assert summary["dominant_contradiction"] == "closure_gap"
    assert summary["prediction"]["operation_or_closure_strict_majority"] is True
    cases[-1]["scientifically_complete"] = False
    assert aggregate(cases)["dominant_contradiction"] is None
