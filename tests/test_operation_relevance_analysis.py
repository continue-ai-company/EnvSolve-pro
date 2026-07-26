from __future__ import annotations

from experiments.analyze_operation_relevance_contract import (
    _aggregate_condition,
    _primary_pass_at_1,
    mechanism_metrics,
    paired_metrics,
)


def _contract() -> dict[str, object]:
    return {
        "schema": "envsolve-operation-relevance-contract-v1",
        "target_finding_ids": ["finding-a"],
        "precondition_evidence_ids": ["evidence-a"],
        "expected_resolved_finding_ids": ["finding-a"],
        "operation_family": {
            "tool": "pip",
            "mechanism": "install",
            "target": "dependency-a",
        },
    }


def _proposal(candidate_id: str) -> dict[str, object]:
    return {
        "event_type": "action_proposed",
        "payload": {
            "action_id": candidate_id,
            "metadata": {
                "operation_contract": _contract(),
                "model_input_projection": {
                    "operation_context": {
                        "active_targets": [
                            {"finding_id": "finding-a"}
                        ],
                        "available_precondition_evidence": [
                            {"evidence_id": "evidence-a"}
                        ],
                    }
                },
            },
        },
    }


def _verification(
    candidate_id: str,
    *,
    passed: bool,
    observed: bool,
) -> dict[str, object]:
    return {
        "event_type": "verification_recorded",
        "payload": {
            "passed": passed,
            "details": {
                "candidate_id": candidate_id,
                "verifier_details": {
                    "report_details": {
                        "goal_report": {
                            "finding_set_complete": True,
                            "findings": [
                                {
                                    "finding_id": "finding-a",
                                    "required": True,
                                    "observed": observed,
                                }
                            ],
                        }
                    }
                },
            },
        },
    }


def test_mechanism_metrics_audit_grounding_progress_and_suppression() -> None:
    events = [
        _proposal("candidate-0001"),
        {"event_type": "action_finished", "payload": {}},
        _verification("candidate-0001", passed=False, observed=False),
        {
            "event_type": "failure_recorded",
            "payload": {
                "category": "candidate-policy-operation-contract",
                "details": {
                    "reason_code": "repeated-family-without-new-evidence"
                },
            },
        },
        _proposal("candidate-0002"),
        {"event_type": "action_finished", "payload": {}},
        _verification("candidate-0002", passed=True, observed=True),
    ]

    result = mechanism_metrics(events, treatment=True)

    assert result["valid"] is True
    assert result["candidate_proposals"] == 2
    assert result["executed_candidates"] == 2
    assert result["operation_contracts"] == 2
    assert result["progress_calibration"] == {
        "met": 1,
        "not_met": 1,
        "unknown": 0,
    }
    assert result["suppression_events"] == 1
    assert result["later_internal_goal_pass_observed"] is True


def test_unknown_target_audit_separates_omission_from_hallucination() -> None:
    events = [
        _verification("candidate-0001", passed=False, observed=False),
        {
            "event_type": "failure_recorded",
            "payload": {
                "category": "candidate-policy-operation-contract",
                "details": {
                    "reason_code": "unknown-target",
                    "unknown_target_ids": ["finding-a", "finding-invented"],
                },
            },
        },
    ]

    result = mechanism_metrics(events, treatment=True)

    assert result["unknown_target_rejection_audit"] == {
        "rejected_target_ids": 2,
        "active_but_unexposed_ids": 1,
        "not_active_ids": 1,
    }


def test_mechanism_metrics_rejects_unexposed_evidence_reference() -> None:
    proposal = _proposal("candidate-0001")
    proposal["payload"]["metadata"]["operation_contract"][
        "precondition_evidence_ids"
    ] = ["not-visible"]

    result = mechanism_metrics([proposal], treatment=True)

    assert result["valid"] is False
    assert result["progress_calibration"]["unknown"] == 1
    assert "evidence IDs absent from model input" in result["errors"][0]


def test_paired_metrics_counts_treatment_only_official_repair() -> None:
    runs = [
        {
            "case_block": 1,
            "condition": "operation-contract-v1",
            "scientifically_eligible": True,
            "official_pass": True,
            "descriptive_terminal": "official_pass",
            "mechanism": {
                "first_internal_goal_failure_observed": True,
            },
        },
        {
            "case_block": 1,
            "condition": "frozen-fresh-control",
            "scientifically_eligible": True,
            "official_pass": False,
            "descriptive_terminal": "official_fail",
            "mechanism": {
                "first_internal_goal_failure_observed": False,
            },
        },
    ]

    result = paired_metrics(runs)

    assert result["eligible_blocks"] == 1
    assert result["treatment_only_pass"] == 1
    assert result["treatment_only_official_repair"] == 1


def test_execution_timeout_is_primary_nonpass_not_infrastructure_censor() -> None:
    treatment = {
        "case_block": 1,
        "condition": "operation-contract-v1",
        "scientifically_eligible": True,
        "official_pass": None,
        "descriptive_terminal": "execution_timeout_unknown",
        "mechanism": {"first_internal_goal_failure_observed": True},
    }
    control = {
        "case_block": 1,
        "condition": "frozen-fresh-control",
        "scientifically_eligible": True,
        "official_pass": True,
        "descriptive_terminal": "official_pass",
        "mechanism": {"first_internal_goal_failure_observed": False},
    }

    assert _primary_pass_at_1(treatment) is False
    result = paired_metrics([treatment, control])

    assert result["eligible_blocks"] == 1
    assert result["control_only_pass"] == 1
    assert result["censored_blocks"] == 0


def test_provider_capacity_is_primary_censor() -> None:
    run = {
        "scientifically_eligible": True,
        "descriptive_terminal": "provider_capacity_unknown",
    }

    assert _primary_pass_at_1(run) is None


def test_condition_aggregate_reports_terminal_reach_and_resources() -> None:
    mechanism = {
        "candidate_proposals": 2,
        "executed_candidates": 2,
        "operation_contracts": 2,
        "policy_rejections_by_reason": {},
        "unknown_target_rejection_audit": {
            "rejected_target_ids": 0,
            "active_but_unexposed_ids": 0,
            "not_active_ids": 0,
        },
        "suppression_events": 0,
        "progress_calibration": {"met": 1, "not_met": 1, "unknown": 0},
        "later_internal_goal_pass_observed": True,
        "first_internal_goal_failure_observed": True,
    }
    runs = [
        {
            "condition": "operation-contract-v1",
            "scientifically_eligible": True,
            "official_pass": True,
            "descriptive_terminal": "official_pass",
            "resources": {
                "total_tokens": 100,
                "requests_started": 2,
                "environments": 2,
                "commands": 2,
            },
            "mechanism": mechanism,
        }
    ]

    result = _aggregate_condition(runs, "operation-contract-v1")

    assert result["official_terminal_reach"] == 1
    assert result["primary_pass_at_1"] == 1
    assert result["primary_nonpass_at_1"] == 0
    assert result["primary_censored"] == 0
    assert result["terminal_classes"] == {"official_pass": 1}
    assert result["resources"]["total_tokens"] == 100
