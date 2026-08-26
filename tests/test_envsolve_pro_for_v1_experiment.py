from __future__ import annotations

import json
from pathlib import Path

from experiments.run_schedule import _validate_schedule


def test_geoapps_replacement_tracks_original_positions_separately() -> None:
    schedule_path = (
        Path(__file__).resolve().parents[1]
        / "experiments/schedules/envsolve_pro_for_v1_geoapps_infra_retry1.json"
    )
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))

    _validate_schedule(schedule_path, schedule)

    assert [episode["position"] for episode in schedule["episodes"]] == [1, 2, 3]
    assert [episode["original_position"] for episode in schedule["episodes"]] == [
        10,
        11,
        12,
    ]
