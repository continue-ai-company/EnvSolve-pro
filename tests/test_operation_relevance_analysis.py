from __future__ import annotations

from experiments.analyze_operation_relevance_contract import (
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
            "mechanism": {
                "first_internal_goal_failure_observed": True,
            },
        },
        {
            "case_block": 1,
            "condition": "frozen-fresh-control",
            "scientifically_eligible": True,
            "official_pass": False,
            "mechanism": {
                "first_internal_goal_failure_observed": False,
            },
        },
    ]

    result = paired_metrics(runs)

    assert result["eligible_blocks"] == 1
    assert result["treatment_only_pass"] == 1
    assert result["treatment_only_official_repair"] == 1
