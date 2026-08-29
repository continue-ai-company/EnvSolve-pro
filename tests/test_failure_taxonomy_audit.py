from __future__ import annotations

from experiments.audit_failure_taxonomy import audit


def _taxonomy() -> dict:
    return {
        "dimensions": {
            "primary_failure_layer": {
                "observation": "O",
                "constraint": "C",
                "operation": "P",
                "unresolved": "U",
            },
            "censoring": {
                "infrastructure_unknown": "I",
                "protocol_censored": "X",
            },
        },
        "method_profiles": {"method-a": {"mechanisms": ["F"]}},
    }


def _matrix() -> dict:
    return {
        "records": [
            {
                "case_id": "case-a",
                "method": "method-a",
                "generation_run_id": "run-a",
                "evaluation_run_id": "run-a",
                "terminal_stage": "public_goal_residual",
            },
            {
                "case_id": "case-b",
                "method": "method-a",
                "generation_run_id": "run-b",
                "evaluation_run_id": "run-b",
                "terminal_stage": "success",
            },
        ]
    }


def _annotations() -> dict:
    return {
        "study_id": "study",
        "status": "provisional-single-reviewer",
        "records": [
            {
                "case_id": "case-a",
                "method": "method-a",
                "generation_run_id": "run-a",
                "evaluation_run_id": "run-a",
                "terminal_stage": "public_goal_residual",
                "primary_layer": "observation",
                "evidence": [
                    {
                        "run_id": "run-a",
                        "relative_path": "evaluation/result.json",
                        "anchor": "missing import remained",
                    }
                ],
            }
        ],
    }


def test_audit_separates_method_profile_from_failure_layer() -> None:
    result = audit(_matrix(), _annotations(), _taxonomy())

    assert result["valid"] is True
    assert result["coverage"]["algorithmic_rows"] == 1
    assert result["algorithmic_distribution"]["observation"] == {
        "count": 1,
        "share": 1.0,
    }
    assert result["by_method"]["method-a"]["profile"] == {
        "mechanisms": ["F"]
    }


def test_audit_excludes_censoring_from_algorithmic_distribution() -> None:
    annotations = _annotations()
    annotations["records"][0]["primary_layer"] = "infrastructure_unknown"

    result = audit(_matrix(), annotations, _taxonomy())

    assert result["coverage"]["algorithmic_rows"] == 0
    assert result["coverage"]["censored_rows"] == 1
    assert result["algorithmic_distribution"]["observation"]["count"] == 0


def test_audit_excludes_unresolved_from_oco_denominator() -> None:
    annotations = _annotations()
    annotations["records"][0]["primary_layer"] = "unresolved"

    result = audit(_matrix(), annotations, _taxonomy())

    assert result["coverage"]["algorithmic_rows"] == 0
    assert result["coverage"]["unresolved_rows"] == 1


def test_audit_reports_missing_artifact_without_changing_causal_label(tmp_path) -> None:
    result = audit(
        _matrix(), _annotations(), _taxonomy(), run_roots=[tmp_path]
    )

    assert result["valid"] is True
    assert result["evidence_artifacts"] == {"not_found_in_supplied_roots": 1}
    assert result["evidence_artifacts_by_method"] == {
        "method-a": {"not_found_in_supplied_roots": 1}
    }


def test_audit_resolves_artifact_below_case_directory(tmp_path) -> None:
    artifact = tmp_path / "run-a" / "case-a" / "evaluation" / "result.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}", encoding="utf-8")

    result = audit(
        _matrix(), _annotations(), _taxonomy(), run_roots=[tmp_path]
    )

    assert result["evidence_artifacts"] == {"found": 1}


def test_audit_rejects_cross_layer_as_a_primary_label() -> None:
    annotations = _annotations()
    annotations["records"][0]["primary_layer"] = "cross-layer"

    result = audit(_matrix(), annotations, _taxonomy())

    assert result["valid"] is False
    assert result["structural_errors"][0]["error"] == "invalid_primary_layer"
