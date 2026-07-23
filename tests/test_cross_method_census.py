from __future__ import annotations

import json
from pathlib import Path

from envsolve_harness.core.config import load_harness_config
from envsolve_harness.utils.provenance import sha256_file
from experiments.run_schedule import _validate_schedule


ROOT = Path(__file__).resolve().parents[1]
VALIDATIONS = ROOT / "experiments/validations"
BASELINE_PATCHES = ROOT / "experiments/baseline_patches"
SCHEDULES = (
    VALIDATIONS / "pro_cross_method_census_v1_codex_schedule.json",
    VALIDATIONS / "pro_cross_method_census_v1_envsolve_schedule.json",
    VALIDATIONS / "pro_cross_method_census_v1_repo2run_lane1_schedule.json",
    VALIDATIONS / "pro_cross_method_census_v1_repo2run_lane2_schedule.json",
)
FINAL_REPO2RUN_SCHEDULES = (
    VALIDATIONS
    / "pro_cross_method_census_v1_repo2run_final_lane1_schedule.json",
    VALIDATIONS
    / "pro_cross_method_census_v1_repo2run_final_lane2_schedule.json",
)
FINAL_ADAPTER_COMMIT = "ab2c3b24ed82ecffd4e7479af2d78dbb3c32e174"
FINAL_ADAPTER_FREEZE = (
    VALIDATIONS
    / "pro_cross_method_census_v1_repo2run_final_adapter_freeze.json"
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


def test_repo2run_infrastructure_amendment_is_case_independent() -> None:
    amendment = json.loads(
        (
            VALIDATIONS
            / "pro_cross_method_census_v1_repo2run_infrastructure_amendment.json"
        ).read_text()
    )
    patch = (
        BASELINE_PATCHES / "repo2run_pin_pipdeptree_2_28_0.patch"
    ).read_text()
    ownership_patch = (
        BASELINE_PATCHES / "repo2run_remove_host_chown.patch"
    ).read_text()
    addfile_patch = (
        BASELINE_PATCHES / "repo2run_isolate_addfile_export.patch"
    ).read_text()
    completion_patch = (
        BASELINE_PATCHES / "repo2run_expand_completion_window.patch"
    ).read_text()
    patch_mount_isolation = (
        BASELINE_PATCHES / "repo2run_isolate_patch_mount.patch"
    ).read_text()

    assert amendment["claim_scope"] == "Baseline execution compatibility only"
    assert amendment["effective_attempt_suffix"] == "infra-retry6"
    assert len(amendment["invalid_for_method_comparison"]) == 6
    assert patch.count("pipdeptree==2.28.0") == 4
    assert "TemporaryDirectory" in addfile_patch
    assert "max_tokens=8192" in completion_patch
    added_lines = [
        line
        for line in (
            patch
            + ownership_patch
            + addfile_patch
            + completion_patch
            + patch_mount_isolation
        ).splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    assert all("sudo" not in line for line in added_lines)
    assert "REPO2RUN_PATCH_DIR" in patch_mount_isolation
    assert 'return os.path.join("/tmp/patch"' in patch_mount_isolation
    assert "envbench-" not in patch
    assert "prompt" not in patch.lower()


def test_final_repo2run_schedules_preserve_cases_and_freeze_adapter() -> None:
    selection = json.loads(
        (VALIDATIONS / "pro_cross_method_census_v1_selection.json").read_text()
    )
    expected_cases = set(selection["case_ids"])
    observed_cases: set[str] = set()
    observed_runs: set[str] = set()

    for path in FINAL_REPO2RUN_SCHEDULES:
        schedule = json.loads(path.read_text())
        _validate_schedule(path, schedule)
        assert schedule["implementation_commit"] == FINAL_ADAPTER_COMMIT
        assert schedule["adapter_freeze"]["algorithm_behavior_changed"] is False
        for episode in schedule["episodes"]:
            assert episode["checkout"] == FINAL_ADAPTER_COMMIT
            assert episode["run_id"].endswith("-final-adapter-v1")
            observed_cases.add(episode["case_id"])
            assert episode["run_id"] not in observed_runs
            observed_runs.add(episode["run_id"])

    assert observed_cases == expected_cases
    assert len(observed_runs) == 16


def test_final_repo2run_adapter_freeze_binds_only_eligible_runs() -> None:
    freeze = json.loads(FINAL_ADAPTER_FREEZE.read_text())
    assert freeze["adapter_boundary"] == {
        "algorithm_behavior_changed": False,
        "case_data_changed": False,
        "command_parser_changed": False,
        "evaluator_changed": False,
        "model_changed": False,
        "model_loop_changed": False,
        "prompt_changed": False,
        "scope": "Repository-independent execution compatibility only",
    }
    assert freeze["qualification"]["result"] == "qualified"
    assert freeze["qualification"]["retry1"]["evaluation_completed"] is True
    assert freeze["qualification"]["retry1"]["exit_code"] == 0
    assert freeze["qualification"]["retry1"]["issues_count"] == 57
    assert (
        freeze["result_eligibility"]["qualification_used_for_method_comparison"]
        is False
    )

    frozen_schedules = freeze["final_execution"]["schedules"]
    assert set(frozen_schedules) == {
        str(path.relative_to(ROOT)) for path in FINAL_REPO2RUN_SCHEDULES
    }
    for path in FINAL_REPO2RUN_SCHEDULES:
        assert frozen_schedules[str(path.relative_to(ROOT))] == sha256_file(path)
