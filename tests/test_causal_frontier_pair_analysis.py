from pathlib import Path
import hashlib
import json

from experiments.analyze_causal_frontier_pairs import (
    TARGETS,
    _matches,
    aggregate,
    target_metrics,
)


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_runtime_targets_match_the_causal_frontier_schema() -> None:
    root = {
        "root_kind": "runtime_compatibility_frontier",
        "provider": "pyo3",
        "subject": "python",
        "observed_version": "3.13",
        "maximum_supported_version": "3.12",
    }

    assert _matches(root, TARGETS["langchain-ai/langgraph"])
    assert _matches(root, TARGETS["nonebot/nonebot2"])


def test_target_metrics_requires_later_absence_for_closure() -> None:
    timeline = [
        {
            "phase": "decision",
            "after_candidate_index": 0,
            "target_present": False,
        },
        {
            "phase": "decision",
            "after_candidate_index": 1,
            "target_present": True,
        },
        {
            "phase": "decision",
            "after_candidate_index": 2,
            "target_present": True,
        },
        {
            "phase": "terminal",
            "after_candidate_index": 3,
            "target_present": False,
        },
    ]

    result = target_metrics(timeline)

    assert result == {
        "target_observed": True,
        "target_first_observed_after_candidate": 1,
        "target_recurrence_decisions": 2,
        "target_closed": True,
        "target_closed_by_candidate": 3,
    }


def _episode(
    pair: int,
    condition: str,
    *,
    success: bool,
    closed: bool,
) -> dict:
    return {
        "pair": pair,
        "condition": condition,
        "repository": f"owner/repo-{pair}",
        "official_pass": success,
        "measurement_integrity_ok": True,
        "target_metrics": {
            "target_observed": True,
            "target_first_observed_after_candidate": 1,
            "target_recurrence_decisions": 1,
            "target_closed": closed,
            "target_closed_by_candidate": 2 if closed else None,
        },
    }


def test_aggregate_applies_preregistered_proceed_rule() -> None:
    episodes = [
        _episode(1, "flat", success=False, closed=False),
        _episode(1, "causal-frontier", success=False, closed=True),
        _episode(2, "flat", success=True, closed=True),
        _episode(2, "causal-frontier", success=True, closed=True),
    ]

    result = aggregate(episodes)

    assert result["target_closures"] == {"flat": 1, "causal-frontier": 2}
    assert result["mechanism_improvement_observed"] is True
    assert result["no_paired_official_success_regression"] is True
    assert result["preregistered_proceed_rule_satisfied"] is True


def test_v2_schedule_is_bound_to_the_frozen_consumed_pairing() -> None:
    schedule_path = (
        ROOT
        / "experiments/validations/pro_p5_causal_frontier_paired_v2_schedule.json"
    )
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    preregistration = ROOT / schedule["preregistration"]
    case_file = ROOT / schedule["case_file"]
    preregistered = json.loads(preregistration.read_text(encoding="utf-8"))

    assert schedule["implementation_freeze"] == (
        "d250549dd29745887fe7fd1db4026b4d37aca384"
    )
    assert schedule["preregistration_sha256"] == _sha256(preregistration)
    assert schedule["case_file_sha256"] == _sha256(case_file)
    assert preregistered["analysis"]["script_sha256"] == _sha256(
        ROOT / preregistered["analysis"]["script"]
    )
    assert len(schedule["episodes"]) == 6
    assert len({item["run_id"] for item in schedule["episodes"]}) == 6
    assert sorted(item["position"] for item in schedule["episodes"]) == list(
        range(1, 7)
    )
    for pair in range(1, 4):
        conditions = {
            item["condition"]
            for item in schedule["episodes"]
            if item["pair"] == pair
        }
        assert conditions == {"flat", "causal-frontier"}


def test_v2_retry3_replaces_only_retry2_infrastructure_censoring() -> None:
    retry2_path = (
        ROOT
        / "experiments/validations/"
        "pro_p5_causal_frontier_paired_v2_infra_retry2_schedule.json"
    )
    retry3_path = (
        ROOT
        / "experiments/validations/"
        "pro_p5_causal_frontier_paired_v2_infra_retry3_schedule.json"
    )
    retry2 = json.loads(retry2_path.read_text(encoding="utf-8"))
    retry3 = json.loads(retry3_path.read_text(encoding="utf-8"))

    assert retry3["source_schedule_sha256"] == _sha256(retry2_path)
    assert retry3["implementation_freeze"] == retry2["implementation_freeze"]
    assert retry3["execution"]["positions_to_execute"] == [1, 4]
    assert retry3["execution"]["execution_order"] == [1, 4]
    assert retry3["execution"]["execution_mode"] == "single sequential lane"
    assert retry3["execution"]["retained_source_positions"] == [2, 3, 5, 6]

    retry_positions = {
        item["position"]: item for item in retry3["source_censoring"]
    }
    assert set(retry_positions) == {1, 4}
    assert all(
        item["terminal_class"] == "dependency-acquisition-infrastructure"
        and item["signature"] == "read-timeout"
        for item in retry_positions.values()
    )
    assert [item["position"] for item in retry3["episodes"]] == list(range(1, 7))
    assert len({item["run_id"] for item in retry3["episodes"]}) == 6
    assert {
        item["position"]
        for item in retry3["episodes"]
        if item["attempt_role"] == "infrastructure-retry"
    } == {1, 4}
