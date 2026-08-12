from __future__ import annotations

import copy

import pytest

from envsolve_harness.dev_bad_case_analysis import (
    select_core_batch,
    validate_classifications,
)


def _taxonomy() -> dict[str, object]:
    return {
        "terminal_outcomes": {
            "official_pass": {"bad_case": False},
            "official_fail": {"bad_case": True},
            "agent_noncompletion": {"bad_case": True},
            "qualification_fail": {"bad_case": True},
            "infrastructure_unknown": {"bad_case": False},
        },
        "failure_layers": {
            "observation": {"subtypes": ["missing-evidence"]},
            "constraint": {"subtypes": ["wrong-version"]},
            "operation": {"subtypes": ["bad-transition"]},
            "cross-layer": {"subtypes": ["interaction"]},
            "unresolved": {"subtypes": ["insufficient-evidence"]},
        },
        "batch_selection": {
            "eligible_terminal_outcomes": [
                "official_fail",
                "agent_noncompletion",
                "qualification_fail",
            ],
            "batch_size": 4,
        },
    }


def _bad(case_id: str, layer: str, subtype: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "adjudication_status": "complete",
        "terminal_outcome": "official_fail",
        "primary_failure_layer": layer,
        "primary_subtype": subtype,
        "secondary_subtypes": [],
        "evidence_anchors": [
            {
                "artifact_path": f"runs/{case_id}/trace.jsonl",
                "observation": "The decisive failure is visible in command 3.",
            }
        ],
    }


def _pass(case_id: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "adjudication_status": "complete",
        "terminal_outcome": "official_pass",
        "primary_failure_layer": None,
        "primary_subtype": None,
        "secondary_subtypes": [],
        "evidence_anchors": [],
    }


def test_requires_evidence_for_non_unresolved_failure() -> None:
    record = _bad("case-a", "constraint", "wrong-version")
    record["evidence_anchors"] = []

    with pytest.raises(ValueError, match="lacks evidence"):
        validate_classifications([record], _taxonomy())


def test_rejects_failure_labels_on_non_bad_terminal() -> None:
    record = _pass("case-a")
    record["primary_failure_layer"] = "constraint"
    record["primary_subtype"] = "wrong-version"

    with pytest.raises(ValueError, match="cannot carry failure labels"):
        validate_classifications([record], _taxonomy())


def test_requires_complete_exact_universe() -> None:
    with pytest.raises(ValueError, match="universe mismatch"):
        validate_classifications(
            [_pass("case-a")],
            _taxonomy(),
            expected_case_ids={"case-a", "case-b"},
        )


def test_selection_is_deterministic_stratified_and_excludes_passes() -> None:
    records = [
        _bad("case-a", "constraint", "wrong-version"),
        _bad("case-b", "constraint", "wrong-version"),
        _bad("case-c", "constraint", "wrong-version"),
        _bad("case-d", "operation", "bad-transition"),
        _bad("case-e", "observation", "missing-evidence"),
        _pass("case-pass"),
    ]
    expected = {str(record["case_id"]) for record in records}

    first = select_core_batch(records, _taxonomy(), expected_case_ids=expected)
    second = select_core_batch(
        list(reversed(copy.deepcopy(records))),
        _taxonomy(),
        expected_case_ids=expected,
    )

    assert first == second
    assert len(first["selected_case_ids"]) == 4
    assert "case-pass" not in first["selected_case_ids"]
    assert first["strata"][0]["stratum"] == ("official_fail|constraint|wrong-version")
    assert set(first["selected_case_ids"][:3]) == {
        first["strata"][0]["ranked_case_ids"][0],
        "case-d",
        "case-e",
    }
    assert set(first["selected_case_ids"]) | set(first["validation_case_ids"]) == {
        "case-a",
        "case-b",
        "case-c",
        "case-d",
        "case-e",
    }


def test_unresolved_failure_may_lack_evidence_anchor() -> None:
    record = _bad("case-a", "unresolved", "insufficient-evidence")
    record["evidence_anchors"] = []

    validate_classifications([record], _taxonomy())


def test_official_pass_can_retain_separate_boundary_quality_failure() -> None:
    taxonomy = _taxonomy()
    taxonomy["outcome_axes"] = {
        "submission_outcome": ["submitted", "noncompletion"],
        "qualification_outcome": ["pass", "fail", "not_run"],
        "official_outcome": ["pass", "fail", "not_evaluated"],
    }
    taxonomy["quality_flags"] = ["advisory-qualification-fail"]
    taxonomy["terminal_outcomes"]["official_pass"]["required_axes"] = {
        "submission_outcome": ["submitted"],
        "official_outcome": ["pass"],
    }
    record = {
        **_pass("case-a"),
        "submission_outcome": "submitted",
        "qualification_outcome": "fail",
        "official_outcome": "pass",
        "quality_flags": ["advisory-qualification-fail"],
        "quality_evidence": [
            {
                "artifact_path": "runs/case-a/qualification.json",
                "observation": "Official passed while advisory qualification failed.",
            }
        ],
    }

    validate_classifications([record], taxonomy)


def test_terminal_outcome_must_match_official_axis() -> None:
    taxonomy = _taxonomy()
    taxonomy["outcome_axes"] = {
        "submission_outcome": ["submitted", "noncompletion"],
        "qualification_outcome": ["pass", "fail", "not_run"],
        "official_outcome": ["pass", "fail", "not_evaluated"],
    }
    taxonomy["quality_flags"] = []
    taxonomy["terminal_outcomes"]["official_pass"]["required_axes"] = {
        "official_outcome": ["pass"]
    }
    record = {
        **_pass("case-a"),
        "submission_outcome": "submitted",
        "qualification_outcome": "pass",
        "official_outcome": "fail",
        "quality_flags": [],
        "quality_evidence": [],
    }

    with pytest.raises(ValueError, match="inconsistent with official_outcome"):
        validate_classifications([record], taxonomy)
