from __future__ import annotations

from pathlib import Path

import pytest

from envsolve_harness.core.io import read_json
from experiments.analyze_m1b_artifact_replay import (
    _global_arm_final_summary,
    _historical_m1_context,
    classify_result,
)
from experiments.run_m1b_artifact_replay import resolve_candidate, validate_project


ROOT = Path(__file__).resolve().parents[1]
SCHEDULE = ROOT / "experiments/schedules/envsolve_pro_m1b_artifact_replay_v1.json"


def test_fixed_schedule_resolves_17_physical_candidates_and_51_replays() -> None:
    schedule = read_json(SCHEDULE)
    physical = 0
    replay_count = 0
    for project in schedule["projects"]:
        programs = validate_project(project, ROOT)
        physical += len(programs)
        replay_count += sum(len(item["order"]) for item in project["rounds"])
    assert physical == 17
    assert replay_count == 51


def test_grouped_candidate_rejects_unequal_programs(tmp_path: Path) -> None:
    first = tmp_path / "first.sh"
    second = tmp_path / "second.sh"
    first.write_text("echo first\n", encoding="utf-8")
    second.write_text("echo second\n", encoding="utf-8")
    candidate = {
        "candidate_id": "bad-group",
        "sources": [
            {"kind": "submitted-program", "path": "first.sh"},
            {"kind": "submitted-program", "path": "second.sh"},
        ],
    }
    with pytest.raises(ValueError, match="groups unequal programs"):
        resolve_candidate(candidate, tmp_path)


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ({"status": "pass"}, "pass"),
        (
            {
                "status": "infrastructure_error",
                "infrastructure_error": (
                    "dependency acquisition was interrupted by ssl-eof"
                ),
            },
            "acquisition_failure",
        ),
        (
            {
                "status": "fail",
                "verification": {"bootstrap": {"exit_code": 42}},
            },
            "interpreter_condition_mismatch",
        ),
        (
            {
                "status": "fail",
                "verification": {"bootstrap": {"exit_code": 255}},
            },
            "transport_failure",
        ),
        (
            {
                "status": "fail",
                "verification": {
                    "bootstrap": {
                        "exit_code": 1,
                        "stderr": "ERROR: Failed building wheel for example",
                    }
                },
            },
            "dependency_or_build_failure",
        ),
        ({"status": "not_started"}, "not_started"),
    ],
)
def test_result_classification(result: dict[str, object], expected: str) -> None:
    assert classify_result(result) == expected


def test_global_arm_summary_keeps_shared_measurements_visible() -> None:
    projects = [
        {
            "final_artifacts_by_arm": {
                "P": {
                    "artifact_count": 1,
                    "category_counts": {"pass": 3},
                    "physical_measurements_shared_across_aliases": True,
                },
                "R0": {
                    "artifact_count": 1,
                    "category_counts": {"pass": 2, "acquisition_failure": 1},
                    "physical_measurements_shared_across_aliases": False,
                },
                "R1": {
                    "artifact_count": 1,
                    "category_counts": {"pass": 3},
                    "physical_measurements_shared_across_aliases": False,
                },
            }
        }
    ]

    summary = _global_arm_final_summary(projects)

    assert summary["P"] == {
        "independent_projects": 1,
        "artifact_count": 1,
        "arm_attributed_replays": 3,
        "category_counts": {"pass": 3},
        "projects_with_measurements_shared_across_arm_aliases": 1,
    }
    assert summary["R0"]["category_counts"] == {
        "acquisition_failure": 1,
        "pass": 2,
    }


def test_historical_context_retains_invalid_attempts_and_state_bug() -> None:
    context = _historical_m1_context()

    assert context["invalid_engineering_attempts"]
    assert context["historical_state_persistence_issue"]
    assert context["all_condition_model_usage_not_additive_with_d0_or_d2_breakdowns"]
