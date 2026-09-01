from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/cases/train_rest204.jsonl"
CASES = ROOT / "experiments/cases/dev_pro_strong_ab_census83_v1.jsonl"
SCHEDULE = ROOT / "experiments/schedules/envsolve_pro_strong_ab_census83_v1.json"
AUDIT = (
    ROOT
    / "experiments/validations/"
    "envsolve_pro_strong_ab_census83_v1_exposure_audit.json"
)
PREREGISTRATION = (
    ROOT
    / "experiments/validations/"
    "envsolve_pro_strong_ab_census83_v1_preregistration.json"
)


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_census_partitions_source_without_protected_cases() -> None:
    source = _jsonl(SOURCE)
    cases = _jsonl(CASES)
    audit = json.loads(AUDIT.read_text())
    source_ids = {str(row["case_id"]) for row in source}
    case_ids = [str(row["case_id"]) for row in cases]
    excluded_ids = {
        str(row["case_id"]) for row in audit["excluded_cases"]
    }

    assert len(source_ids) == 204
    assert len(case_ids) == len(set(case_ids)) == 83
    assert len(excluded_ids) == 121
    assert set(case_ids).isdisjoint(excluded_ids)
    assert set(case_ids) | excluded_ids == source_ids
    assert {str(row["split"]) for row in cases} == {
        "dev-pro-strong-ab-census83-v1"
    }


def test_schedule_has_one_a1_and_conditional_paired_followups_per_case() -> None:
    cases = _jsonl(CASES)
    schedule = json.loads(SCHEDULE.read_text())
    plans = schedule["cases"]

    assert schedule["model"] == "gpt-5.6-sol"
    assert schedule["reasoning_effort"] == "xhigh"
    assert len(plans) == len(cases) == 83
    assert [plan["position"] for plan in plans] == list(range(1, 84))
    assert [plan["case_id"] for plan in plans] == [
        row["case_id"] for row in cases
    ]
    assert {plan["construction_host"] for plan in plans} == {
        "agenthub",
        "spark",
    }
    assert sum(plan["construction_host"] == "agenthub" for plan in plans) == 42
    assert sum(plan["construction_host"] == "spark" for plan in plans) == 41

    run_ids: list[str] = []
    for plan in plans:
        assert set(plan["conditional_followup_order"]) == {
            "A2-no-replay",
            "B-same-session-replay",
        }
        assert plan["a1"]["method"] == "codex-cli-goal-aware-boundary-v5"
        assert plan["a2"]["method"] == "codex-cli-goal-aware-boundary-v5"
        assert plan["b"]["method"] == (
            "envsolve-pro-minimal-b-boundary-v5"
        )
        run_ids.extend(
            [plan["a1"]["run_id"], plan["a2"]["run_id"], plan["b"]["run_id"]]
        )
    assert len(run_ids) == len(set(run_ids)) == 249


def test_preregistration_makes_terminal_success_the_decision_metric() -> None:
    prereg = json.loads(PREREGISTRATION.read_text())

    assert prereg["status"] == "recorded_before_first_a1_outcome"
    assert prereg["shared_protocol"]["official_metric"] == "Official Pass@1"
    assert prereg["analysis"]["primary_contrast"].startswith(
        "B-exclusive wins versus A2-exclusive wins"
    )
    assert prereg["analysis"]["frontier_metrics"].startswith("diagnostic only")
    assert prereg["shared_protocol"]["protected_canary_opened"] is False
    assert prereg["shared_protocol"]["official_test_opened"] is False
    assert "No new hash" in prereg["safeguard_policy"]
