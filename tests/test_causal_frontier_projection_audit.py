import hashlib
import json
from pathlib import Path

from experiments.audit_causal_frontier_projection import (
    aggregate,
    audit_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]


def _metadata(snapshot: dict) -> dict:
    encoded = json.dumps(
        snapshot,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "constraint_frontier_snapshot": snapshot,
        "constraint_frontier_sha256": hashlib.sha256(
            encoded.encode("utf-8")
        ).hexdigest(),
    }


def test_structured_persisted_projection_passes_integrity_audit() -> None:
    result = audit_snapshot(
        _metadata(
            {
                "causal_roots": [{"root_kind": "runtime_compatibility_frontier"}],
                "summary": {"causal_root_count": 1},
            }
        )
    )

    assert result["integrity_ok"] is True
    assert result["hash_valid"] is True
    assert result["causal_roots_count"] == 1


def test_required_model_projection_schema_is_enforced() -> None:
    metadata = _metadata(
        {
            "model_projection_schema_version": "1.0.0",
            "causal_roots": [],
            "summary": {"causal_root_count": 0},
        }
    )

    valid = audit_snapshot(metadata, "1.0.0")
    invalid = audit_snapshot(metadata, "2.0.0")

    assert valid["integrity_ok"] is True
    assert invalid["integrity_ok"] is False
    assert invalid["failure_reasons"] == ["model_projection_schema_mismatch"]


def test_complete_root_requirement_rejects_structured_omission() -> None:
    metadata = _metadata(
        {
            "model_projection_schema_version": "1.0.0",
            "causal_roots": [{"subject": "python"}],
            "summary": {"causal_root_count": 2, "causal_roots_omitted": 1},
        }
    )

    result = audit_snapshot(metadata, "1.0.0", require_complete_roots=True)

    assert result["integrity_ok"] is False
    assert result["failure_reasons"] == ["causal_roots_incomplete"]


def test_whole_object_truncation_fails_even_with_a_valid_hash() -> None:
    result = audit_snapshot(
        _metadata(
            {
                "truncated": True,
                "original_chars": 10_409,
                "excerpt": "{...}",
            }
        )
    )

    assert result["integrity_ok"] is False
    assert result["hash_valid"] is True
    assert result["failure_reasons"] == [
        "whole_object_truncated",
        "causal_roots_missing_or_not_list",
        "summary_missing_or_not_object",
    ]


def test_one_invalid_causal_decision_invalidates_effect_analysis() -> None:
    valid = {
        "condition": "causal-frontier",
        "decision_count": 2,
        "invalid_decision_count": 0,
        "decisions": [
            {"failure_reasons": []},
            {"failure_reasons": []},
        ],
    }
    invalid = {
        "condition": "causal-frontier",
        "decision_count": 1,
        "invalid_decision_count": 1,
        "decisions": [
            {"failure_reasons": ["whole_object_truncated"]},
        ],
    }

    result = aggregate([valid, invalid])

    assert result["measurement_integrity_ok"] is False
    assert result["effect_analysis_admissible"] is False
    assert result["failure_reasons"] == ["whole_object_truncated"]


def test_v3_integrity_schedule_is_bound_before_execution() -> None:
    schedule_path = (
        ROOT
        / "experiments/validations/"
        "pro_p5_causal_frontier_v3_integrity_schedule.json"
    )
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    preregistration = ROOT / schedule["preregistration"]
    case_file = ROOT / schedule["case_file"]

    assert schedule["preregistration_sha256"] == hashlib.sha256(
        preregistration.read_bytes()
    ).hexdigest()
    assert schedule["case_file_sha256"] == hashlib.sha256(
        case_file.read_bytes()
    ).hexdigest()
    assert schedule["implementation_freeze"] == (
        "f2193509c856da892c64bd50e1b7e33a88ed01ea"
    )
    assert [item["position"] for item in schedule["episodes"]] == [1, 2, 3]
    assert len({item["run_id"] for item in schedule["episodes"]}) == 3
    assert {item["condition"] for item in schedule["episodes"]} == {
        "causal-frontier"
    }
