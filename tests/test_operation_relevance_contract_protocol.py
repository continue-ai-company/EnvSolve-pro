from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from experiments.tools import (
    build_pro_operation_relevance_contract_v1_schedule as schedule_builder,
    select_pro_operation_relevance_contract_v1 as selector,
)


ROOT = Path(__file__).resolve().parents[1]
FREEZE = (
    ROOT
    / "experiments/protocols/pro_operation_relevance_contract_v1_freeze.json"
)
PREREGISTRATION = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_preregistration.json"
)
AMENDMENT = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_provider_probe_infrastructure_amendment.json"
)
QUALIFICATION_SCHEDULE = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_schedule.json"
)
PRECLOSURE_RESULTS = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_results_preclosure.json"
)
RETRY_AMENDMENT = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_infrastructure_retry1_amendment.json"
)
RETRY_SCHEDULE = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_infrastructure_retry1_schedule.json"
)
MEASUREMENT_AMENDMENT = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_measurement_amendment.json"
)
DIRECT_PREREGISTRATION = (
    ROOT
    / "experiments/validations/pro_operation_relevance_contract_v1_deepseek_direct_replication_preregistration.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_algorithm_freeze_hashes_match_without_mutating_frozen_baseline() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))

    for group in (
        "algorithm_files",
        "preserved_baseline_files",
        "design_files",
    ):
        for relative, expected in freeze[group].items():
            assert _sha256(ROOT / relative) == expected, relative


def test_preregistration_binds_inputs_before_case_selection() -> None:
    preregistration = json.loads(
        PREREGISTRATION.read_text(encoding="utf-8")
    )

    assert preregistration["algorithm_freeze"]["sha256"] == _sha256(FREEZE)
    for key in ("source_case_file", "consumed_exclusion_file"):
        path = ROOT / preregistration["selection"][key]
        assert _sha256(path) == preregistration["selection"][f"{key}_sha256"]
    for key in ("config", "protocol"):
        path = ROOT / preregistration["shared_contract"][key]
        assert _sha256(path) == preregistration["shared_contract"][
            f"{key}_sha256"
        ]
    assert (
        preregistration["analysis"][
            "no_algorithm_prompt_or_threshold_change_after_selection"
        ]
        is True
    )


def test_provider_closure_matches_preregistered_infrastructure_retry() -> None:
    closure = json.loads(
        selector.PROVIDER_CLOSURE.read_text(encoding="utf-8")
    )
    amendment = json.loads(AMENDMENT.read_text(encoding="utf-8"))
    completed = 0
    parsed = 0
    request_errors = 0

    assert closure["result"] == {
        "qualified": True,
        "required_normal_parsed_responses": 3,
        "normal_parsed_responses": 3,
        "policy_contract_failures": 0,
        "infrastructure_censored_requests": 1,
        "censored_request_retried": True,
    }
    assert closure["amendment"]["sha256"] == _sha256(AMENDMENT)
    assert (
        amendment["combined_gate"]["closure_output"]
        == str(selector.PROVIDER_CLOSURE.relative_to(ROOT))
    )
    for source in closure["sources"]:
        source_path = ROOT / source["path"]
        probe = json.loads(source_path.read_text(encoding="utf-8"))
        assert _sha256(source_path) == source["sha256"]
        assert (
            probe["result"]["usage"]["responses_completed"]
            == source["completed_responses"]
        )
        assert (
            probe["result"]["parsed_candidates"]
            == source["parsed_candidates"]
        )
        assert (
            probe["result"]["usage"]["request_errors"]
            == source["request_errors"]
        )
        assert sorted(
            error["error_type"] for error in probe["result"]["errors"]
        ) == sorted(source["error_types"])
        assert probe["privacy"]["api_key_persisted"] is False
        completed += source["completed_responses"]
        parsed += source["parsed_candidates"]
        request_errors += source["request_errors"]
    assert completed == parsed == 3
    assert request_errors == 1


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_selected_and_remaining_cases_preserve_repository_partition() -> None:
    selected = _read_jsonl(selector.SELECTED)
    remaining = _read_jsonl(selector.REMAINING)
    excluded = _read_jsonl(selector.EXCLUSIONS)
    provenance = json.loads(selector.PROVENANCE.read_text(encoding="utf-8"))

    selected_repositories = {str(row["repository"]) for row in selected}
    remaining_repositories = {str(row["repository"]) for row in remaining}
    excluded_repositories = {str(row["repository"]) for row in excluded}
    assert len(selected) == len(selected_repositories) == 5
    assert len(remaining) == len(remaining_repositories) == 86
    assert selected_repositories.isdisjoint(remaining_repositories)
    assert selected_repositories.isdisjoint(excluded_repositories)
    assert remaining_repositories.isdisjoint(excluded_repositories)
    assert provenance["selected_sha256"] == _sha256(selector.SELECTED)
    assert provenance["remaining_sha256"] == _sha256(selector.REMAINING)
    assert (
        provenance["provider_closure_sha256"]
        == _sha256(selector.PROVIDER_CLOSURE)
    )


def test_schedule_is_a_complete_deterministic_pairing() -> None:
    schedule = json.loads(
        schedule_builder.OUTPUT.read_text(encoding="utf-8")
    )
    episodes = schedule["episodes"]

    assert len(episodes) == 10
    assert schedule["case_file_sha256"] == _sha256(selector.SELECTED)
    assert schedule["selection_provenance_sha256"] == _sha256(
        selector.PROVENANCE
    )
    assert [episode["position"] for episode in episodes] == list(range(1, 11))
    case_counts = Counter(str(episode["case_id"]) for episode in episodes)
    assert set(case_counts.values()) == {2}
    for case_id in case_counts:
        pair = [
            episode
            for episode in episodes
            if episode["case_id"] == case_id
        ]
        assert {episode["condition"] for episode in pair} == {
            "frozen-fresh-control",
            "operation-contract-v1",
        }
        assert {episode["runner"] for episode in pair} == {
            "envsolve",
            "envsolve-pro",
        }


def test_infrastructure_retry_preserves_episode_identity_and_algorithmic_timeout() -> None:
    source = json.loads(QUALIFICATION_SCHEDULE.read_text(encoding="utf-8"))
    retry = json.loads(RETRY_SCHEDULE.read_text(encoding="utf-8"))
    amendment = json.loads(RETRY_AMENDMENT.read_text(encoding="utf-8"))
    source_by_position = {
        int(episode["position"]): episode for episode in source["episodes"]
    }
    retry_by_position = {
        int(episode["position"]): episode for episode in retry["episodes"]
    }
    retained = {1, 2, 5}
    retried = {3, 4, 6, 7, 8, 9, 10}

    assert retry["source_schedule_sha256"] == _sha256(
        QUALIFICATION_SCHEDULE
    )
    assert retry["preregistration_sha256"] == _sha256(PREREGISTRATION)
    assert retry["case_file_sha256"] == _sha256(selector.SELECTED)
    assert retry["execution"]["retained_positions"] == sorted(retained)
    assert retry["execution"]["execution_ranges"] == [[3, 4], [6, 10]]
    assert amendment["retry_schedule_sha256"] == _sha256(RETRY_SCHEDULE)
    assert amendment["preclosure_results_sha256"] == _sha256(
        PRECLOSURE_RESULTS
    )
    assert {
        int(item["position"]) for item in amendment["source_censoring"]
    } == retried
    assert {
        int(item["position"])
        for item in amendment["retained_source_attempts"]
    } == retained

    identity_fields = (
        "case_block",
        "case_id",
        "condition",
        "method",
        "model",
        "position",
        "runner",
        "seed",
    )
    for position in range(1, 11):
        original = source_by_position[position]
        closure = retry_by_position[position]
        assert {
            field: closure[field] for field in identity_fields
        } == {
            field: original[field] for field in identity_fields
        }
        if position in retained:
            assert closure["attempt_role"] == "retained-source"
            assert closure["run_id"] == original["run_id"]
            assert "source_run_id" not in closure
        else:
            assert closure["attempt_role"] == "infrastructure-retry"
            assert closure["source_run_id"] == original["run_id"]
            assert closure["run_id"] != original["run_id"]


def test_measurement_amendment_preserves_original_and_binds_correction() -> None:
    amendment = json.loads(
        MEASUREMENT_AMENDMENT.read_text(encoding="utf-8")
    )

    for binding in (
        amendment["original_preclosure_results"],
        amendment["corrected_preclosure_results"],
        amendment["corrected_analysis"]["analyzer"],
        amendment["corrected_analysis"]["result_summarizer"],
    ):
        assert _sha256(ROOT / binding["path"]) == binding["sha256"]
    for binding in amendment["corrected_analysis"]["tests"]:
        assert _sha256(ROOT / binding["path"]) == binding["sha256"]
    assert "execution_timeout_unknown" in amendment[
        "frozen_primary_taxonomy"
    ]["method_nonpass"]
    assert "provider_capacity_unknown" in amendment[
        "frozen_primary_taxonomy"
    ]["external_censor"]
    retained = json.loads(RETRY_AMENDMENT.read_text(encoding="utf-8"))[
        "retained_source_attempts"
    ]
    assert any(
        item["position"] == 5
        and "terminal-reach outcome" in item["reason"]
        for item in retained
    )


def test_deepseek_direct_replication_binds_same_model_and_consumed_cases() -> None:
    preregistration = json.loads(
        DIRECT_PREREGISTRATION.read_text(encoding="utf-8")
    )
    canary = preregistration["canary"]
    config = preregistration["config"]
    provider = preregistration["frozen_provider_change"]
    comparison = preregistration["frozen_comparison"]

    assert _sha256(ROOT / canary["path"]) == canary["sha256"]
    assert _sha256(ROOT / config["path"]) == config["sha256"]
    assert _sha256(ROOT / comparison["case_file"]) == comparison[
        "case_file_sha256"
    ]
    assert _sha256(ROOT / comparison["protocol"]) == comparison[
        "protocol_sha256"
    ]
    assert _sha256(ROOT / preregistration["analysis"]["analyzer"]) == (
        preregistration["analysis"]["analyzer_sha256"]
    )
    assert _sha256(ROOT / preregistration["provider_gate"]["script"]) == (
        preregistration["provider_gate"]["script_sha256"]
    )
    canary_result = json.loads(
        (ROOT / canary["path"]).read_text(encoding="utf-8")
    )
    assert canary_result["result"]["qualified"] is True
    assert canary_result["privacy"] == {
        "api_key_persisted": False,
        "candidate_content_persisted": False,
        "reasoning_content_persisted": False,
    }
    assert provider["direct_model_id"] == "deepseek-v4-pro"
    assert provider["direct_model_version"] == "DeepSeek-V4-Pro"
    assert preregistration["claim_scope"].startswith(
        "Consumed-development provider replication."
    )
