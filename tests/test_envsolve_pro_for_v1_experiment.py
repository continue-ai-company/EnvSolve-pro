from __future__ import annotations

import json
from pathlib import Path

from experiments.run_schedule import _validate_schedule


def test_geoapps_replacements_track_original_positions_separately() -> None:
    schedules_root = (
        Path(__file__).resolve().parents[1] / "experiments/schedules"
    )
    schedule_paths = [
        schedules_root / "envsolve_pro_for_v1_geoapps_infra_retry1.json",
        schedules_root / "envsolve_pro_for_v1_geoapps_infra_retry2.json",
    ]

    for schedule_path in schedule_paths:
        schedule = json.loads(schedule_path.read_text(encoding="utf-8"))

        _validate_schedule(schedule_path, schedule)

        assert [episode["position"] for episode in schedule["episodes"]] == [1, 2, 3]
        assert [episode["original_position"] for episode in schedule["episodes"]] == [
            10,
            11,
            12,
        ]
