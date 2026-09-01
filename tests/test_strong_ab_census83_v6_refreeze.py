from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V5 = ROOT / "experiments/schedules/envsolve_pro_strong_ab_census83_v1.json"
V6 = ROOT / "experiments/schedules/envsolve_pro_strong_ab_census83_v6_v1.json"
REFREEZE = ROOT / "experiments/protocols/envsolve_pro_boundary_v6_refreeze.json"
PREREG = (
    ROOT
    / "experiments/validations/envsolve_pro_strong_ab_census83_v6_v1_preregistration.json"
)


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_v6_restarts_the_exact_v5_identity_order_and_host_assignment() -> None:
    v5 = _json(V5)
    v6 = _json(V6)

    assert v6["study_id"] == "envsolve-pro-strong-ab-census83-v6-v1"
    assert v6["config"].endswith("strong_ab_census83_v6_v1.json")
    assert len(v6["cases"]) == 83
    assert [item["case_id"] for item in v6["cases"]] == [
        item["case_id"] for item in v5["cases"]
    ]
    assert [item["construction_host"] for item in v6["cases"]] == [
        item["construction_host"] for item in v5["cases"]
    ]
    assert [item["conditional_followup_order"] for item in v6["cases"]] == [
        item["conditional_followup_order"] for item in v5["cases"]
    ]
    assert all(
        item[arm]["method"].endswith("boundary-v6")
        for item in v6["cases"]
        for arm in ("a1", "a2", "b")
    )
    assert len(
        {
            item[arm]["run_id"]
            for item in v6["cases"]
            for arm in ("a1", "a2", "b")
        }
    ) == 249


def test_v6_refreeze_precedes_results_and_preserves_treatment_parity() -> None:
    refreeze = _json(REFREEZE)
    prereg = _json(PREREG)

    assert refreeze["status"] == "recorded_before_first_v6_result"
    assert prereg["status"] == "recorded_before_first_v6_a1_outcome"
    assert refreeze["treatment_parity"]["unique_difference"] == (
        "same-session replay feedback"
    )
    assert refreeze["scope"]["v5_code_and_results_preserved"] is True
    assert prereg["shared_protocol"]["official_metric"] == "Official Pass@1"
    assert prereg["shared_protocol"]["protected_canary_opened"] is False
    assert prereg["shared_protocol"]["official_test_opened"] is False
