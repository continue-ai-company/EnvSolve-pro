from __future__ import annotations

import json
from pathlib import Path

from envsolve_harness.utils.provenance import sha256_file

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "experiments/cases/"
    "train_untouched_after_pro_minimal_b_v1_paired_53.jsonl"
)
SELECTED = (
    ROOT
    / "experiments/cases/"
    "dev_pro_certification_repair_ablation_v1_8_v1_0_1.jsonl"
)
REMAINING = (
    ROOT
    / "experiments/cases/"
    "train_untouched_after_pro_certification_repair_ablation_v1_37_v1_0_1.jsonl"
)
SCHEDULE = (
    ROOT
    / "experiments/schedules/"
    "pro_certification_repair_ablation_v1_dev8_v1_0_1.json"
)
AUDIT = (
    ROOT
    / "experiments/validations/"
    "pro_certification_repair_ablation_v1_preselection_consumed_repository_audit.json"
)
AMENDMENT = (
    ROOT
    / "experiments/validations/"
    "pro_certification_repair_ablation_v1_dev8_selection_amendment.json"
)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_corrected_selection_partitions_source_by_repository() -> None:
    source = _read_jsonl(SOURCE)
    selected = _read_jsonl(SELECTED)
    remaining = _read_jsonl(REMAINING)
    audit = json.loads(AUDIT.read_text())

    source_repositories = {str(row["repository"]) for row in source}
    selected_repositories = [str(row["repository"]) for row in selected]
    remaining_repositories = {str(row["repository"]) for row in remaining}
    consumed_repositories = {
        str(row["repository"]) for row in audit["consumed_repositories"]
    }

    assert len(source_repositories) == 53
    assert selected_repositories == [
        "gpflow/gpflow",
        "pypa/distutils",
        "basxsoftwareassociation/basxconnect",
        "ecds/readux",
        "valory-xyz/trader",
        "adbar/trafilatura",
        "zappa/zappa",
        "nixtla/neuralforecast",
    ]
    assert len(remaining_repositories) == 37
    assert len(consumed_repositories) == 8
    assert not set(selected_repositories) & consumed_repositories
    assert not remaining_repositories & consumed_repositories
    assert not set(selected_repositories) & remaining_repositories
    assert (
        set(selected_repositories) | remaining_repositories | consumed_repositories
        == source_repositories
    )


def test_corrected_schedule_is_a_complete_paired_three_arm_design() -> None:
    selected = _read_jsonl(SELECTED)
    schedule = json.loads(SCHEDULE.read_text())
    episodes = schedule["episodes"]
    case_to_repository = {
        str(row["case_id"]): str(row["repository"]) for row in selected
    }

    assert schedule["case_file_sha256"] == sha256_file(SELECTED)
    assert [episode["position"] for episode in episodes] == list(range(1, 25))
    assert len({episode["run_id"] for episode in episodes}) == 24
    assert {episode["host"] for episode in episodes} == {"mac"}

    repository_conditions: dict[str, set[str]] = {}
    for episode in episodes:
        repository = case_to_repository[str(episode["case_id"])]
        repository_conditions.setdefault(repository, set()).add(
            str(episode["condition"])
        )
    assert set(repository_conditions) == set(case_to_repository.values())
    assert all(
        conditions
        == {
            "A-strong-agent-control",
            "B-one-shot-certification",
            "C-retryable-minimal-b",
        }
        for conditions in repository_conditions.values()
    )
    assert episodes[3]["run_id"] == (
        "pro-cert-repair-v1-dev8-04R1-C-retryable-minimal-b"
    )


def test_selection_amendment_references_frozen_outputs_by_hash() -> None:
    amendment = json.loads(AMENDMENT.read_text())
    audit_reference = amendment["audit"]
    correction = amendment["correction"]

    assert audit_reference["sha256"] == sha256_file(AUDIT)
    assert correction["selected"]["sha256"] == sha256_file(SELECTED)
    assert correction["untouched_remaining"]["sha256"] == sha256_file(REMAINING)
    assert correction["schedule"]["sha256"] == sha256_file(SCHEDULE)
    assert amendment["execution_boundary"][
        "replacement_case_outcomes_observed_before_freeze"
    ] is False
