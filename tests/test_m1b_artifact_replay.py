from __future__ import annotations

from pathlib import Path

import pytest

from envsolve_harness.core.io import read_json
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
