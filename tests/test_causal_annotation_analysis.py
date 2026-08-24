from __future__ import annotations

import pytest

from experiments.analyze_causal_annotations import join_annotations, summarize


def _matrix() -> dict:
    return {
        "records": [
            {
                "case_id": "case-a",
                "method": "method-a",
                "generation_run_id": "generation-a",
                "evaluation_run_id": "evaluation-a",
                "terminal_stage": "target_bootstrap",
            },
            {
                "case_id": "case-b",
                "method": "method-b",
                "generation_run_id": "generation-b",
                "evaluation_run_id": "evaluation-b",
                "terminal_stage": "success",
            },
        ]
    }


def _annotations() -> dict:
    return {
        "study_id": "study",
        "status": "provisional-single-reviewer",
        "claim_scope": "development only",
        "records": [
            {
                "case_id": "case-a",
                "method": "method-a",
                "generation_run_id": "generation-a",
                "evaluation_run_id": "evaluation-a",
                "terminal_stage": "target_bootstrap",
                "primary_layer": "observation",
                "evidence": [{"anchor": "target-only fact"}],
            }
        ],
    }


def test_summary_counts_annotations_without_treating_passes_as_failures() -> None:
    result = summarize(_matrix(), _annotations())

    assert result["coverage"] == {
        "matrix_rows": 2,
        "non_success_rows": 1,
        "annotated_rows": 1,
        "remaining_non_success_rows": 0,
    }
    assert result["primary_layer_counts"] == {"observation": 1}
    assert result["by_method"] == {"method-a": {"observation": 1}}


def test_join_rejects_annotation_without_matching_matrix_row() -> None:
    annotations = _annotations()
    annotations["records"][0]["case_id"] = "unknown"

    with pytest.raises(ValueError, match="no evidence-matrix row"):
        join_annotations(_matrix(), annotations)


def test_join_rejects_terminal_stage_drift() -> None:
    annotations = _annotations()
    annotations["records"][0]["terminal_stage"] = "public_goal_residual"

    with pytest.raises(ValueError, match="Terminal-stage mismatch"):
        join_annotations(_matrix(), annotations)


def test_join_requires_an_evidence_anchor() -> None:
    annotations = _annotations()
    annotations["records"][0]["evidence"] = []

    with pytest.raises(ValueError, match="no evidence anchors"):
        join_annotations(_matrix(), annotations)
