#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VALIDATIONS = ROOT / "experiments/validations"
IMPLEMENTATION_COMMIT = "ab2c3b24ed82ecffd4e7479af2d78dbb3c32e174"
RUN_SUFFIX = "final-adapter-v1"
EXTERNAL_BASELINE_DIFF_SHA256 = (
    "9c68d20845dc2d0d71c3b46ff1f4f03006471352a615ec4bbb53c47b877a1f1f"
)
HARNESS_ADAPTER_SHA256 = (
    "4de53b370a9ac06fce67c5c64299a5f40d0a0f73f0ef9c17f07aaef45fafcbe1"
)
SCHEDULES = {
    "pro_cross_method_census_v1_repo2run_lane1_schedule.json":
        "pro_cross_method_census_v1_repo2run_final_lane1_schedule.json",
    "pro_cross_method_census_v1_repo2run_lane2_schedule.json":
        "pro_cross_method_census_v1_repo2run_final_lane2_schedule.json",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def amended_schedule(source: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(source)
    result["schedule_id"] = f"{source['schedule_id']}-{RUN_SUFFIX}"
    result["implementation_commit"] = IMPLEMENTATION_COMMIT
    result["adapter_freeze"] = {
        "kind": "baseline-execution-compatibility-only",
        "implementation_commit": IMPLEMENTATION_COMMIT,
        "external_baseline_diff_sha256": EXTERNAL_BASELINE_DIFF_SHA256,
        "harness_adapter_path": "envsolve_harness/scripts/repo2run.py",
        "harness_adapter_sha256": HARNESS_ADAPTER_SHA256,
        "algorithm_behavior_changed": False,
    }
    for episode in result["episodes"]:
        episode["checkout"] = IMPLEMENTATION_COMMIT
        episode["run_id"] = f"{episode['run_id']}-{RUN_SUFFIX}"
    return result


def main() -> None:
    observed: set[str] = set()
    for source_name, output_name in SCHEDULES.items():
        schedule = amended_schedule(read_json(VALIDATIONS / source_name))
        run_ids = {str(episode["run_id"]) for episode in schedule["episodes"]}
        if observed & run_ids:
            raise ValueError("Final Repo2Run schedules contain duplicate run IDs")
        observed.update(run_ids)
        write_json(VALIDATIONS / output_name, schedule)
    if len(observed) != 16:
        raise ValueError("Final Repo2Run schedules must cover exactly 16 cases")


if __name__ == "__main__":
    main()
