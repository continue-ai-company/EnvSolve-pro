from __future__ import annotations

from experiments.build_blinded_causal_annotation_packet import build_packet
from experiments.compare_causal_annotations import compare


def _matrix() -> dict:
    return {
        "study_id": "study",
        "records": [
            {
                "case_id": "case-a",
                "method": "method-a",
                "generation_run_id": "generation-a",
                "evaluation_run_id": "evaluation-a",
                "terminal_stage": "public_goal_residual",
                "official_pass": False,
            },
            {
                "case_id": "case-b",
                "method": "method-b",
                "generation_run_id": "generation-b",
                "evaluation_run_id": "evaluation-b",
                "terminal_stage": "success",
                "official_pass": True,
            },
        ],
    }


def test_blinded_packet_excludes_first_reviewer_inference() -> None:
    packet = build_packet(_matrix())

    assert packet["coverage"] == {
        "matrix_rows": 2,
        "non_success_rows": 1,
        "packet_rows": 1,
    }
    record = packet["records"][0]
    assert record["annotation"]["primary_layer"] is None
    assert "rationale" not in record or record["rationale"] is None
    assert "subtype" not in record or record["subtype"] is None


def test_agreement_reports_exact_rate_and_cohen_kappa() -> None:
    packet = build_packet(_matrix())
    first = {
        "records": [
            {
                **{
                    field: packet["records"][0][field]
                    for field in (
                        "case_id",
                        "method",
                        "generation_run_id",
                        "evaluation_run_id",
                    )
                },
                "primary_layer": "observation",
            }
        ]
    }
    packet["records"][0]["annotation"]["primary_layer"] = "observation"

    result = compare(first, packet)

    assert result["coverage"]["compared_rows"] == 1
    assert result["agreement"]["exact_rate"] == 1.0
    assert result["agreement"]["cohen_kappa"] == 1.0


def test_agreement_leaves_unfilled_second_packet_unscored() -> None:
    packet = build_packet(_matrix())
    first = {
        "records": [
            {
                **{
                    field: packet["records"][0][field]
                    for field in (
                        "case_id",
                        "method",
                        "generation_run_id",
                        "evaluation_run_id",
                    )
                },
                "primary_layer": "observation",
            }
        ]
    }

    result = compare(first, packet)

    assert result["coverage"]["missing_second_labels"] == 1
    assert result["agreement"] is None
