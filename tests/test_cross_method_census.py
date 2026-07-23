from __future__ import annotations

import json
from pathlib import Path

from envsolve_harness.core.config import load_harness_config
from envsolve_harness.utils.provenance import sha256_file
from experiments.run_schedule import _validate_schedule


ROOT = Path(__file__).resolve().parents[1]
VALIDATIONS = ROOT / "experiments/validations"
SCHEDULES = (
    VALIDATIONS / "pro_cross_method_census_v1_codex_schedule.json",
    VALIDATIONS / "pro_cross_method_census_v1_envsolve_schedule.json",
    VALIDATIONS / "pro_cross_method_census_v1_repo2run_lane1_schedule.json",
    VALIDATIONS / "pro_cross_method_census_v1_repo2run_lane2_schedule.json",
)


def test_cross_method_schedules_cover_three_methods_and_sixteen_cases() -> None:
    selection = json.loads(
        (VALIDATIONS / "pro_cross_method_census_v1_selection.json").read_text()
    )
    case_ids = set(selection["case_ids"])
    observed: dict[str, set[str]] = {}

    for path in SCHEDULES:
        schedule = json.loads(path.read_text())
        _validate_schedule(path, schedule)
        assert selection["schedules"][path.name] == sha256_file(path)
        for episode in schedule["episodes"]:
            observed.setdefault(episode["method_id"], set()).add(episode["case_id"])

    assert observed["codex-cli-native"] == case_ids
    assert observed["envsolve-pro-causal-v3"] == case_ids
    assert observed["repo2run-reproduced-open"] == case_ids


def test_cross_method_configs_load_with_expected_roots() -> None:
    mac = load_harness_config(
        ROOT / "experiments/configs/local_mac_pro_cross_method_v1.json",
        ROOT,
    )
    spark = load_harness_config(
        ROOT / "experiments/configs/local_spark_pro_cross_method_v1.json",
        ROOT,
    )

    assert "codex-cli" in mac.solver_roots
    assert {"envbench-agent", "repo2run"} <= set(spark.solver_roots)
    assert mac.envsolve_max_candidates == spark.envsolve_max_candidates == 8
