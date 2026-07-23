import hashlib
import json

from experiments.audit_causal_frontier_projection import (
    aggregate,
    audit_snapshot,
)


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
