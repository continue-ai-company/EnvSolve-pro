from __future__ import annotations

import json
from pathlib import Path

from experiments.analyze_compatibility_ledger_pilot import (
    _apply_replacement_schedules,
    _apply_cross_arm_validity,
    _adjudicate,
    _candidate_event,
    _episode,
    _pairs,
    _terminal_provider_failure,
    _usage,
)
from envsolve_harness.storage.artifacts import safe_name


def test_episode_censors_official_host_launcher_failure(tmp_path: Path) -> None:
    spec = {
        "position": 3,
        "run_id": "run-3",
        "case_id": "case@revision",
        "pair_id": "pair-1",
        "replication": 1,
        "arm": "D-LEDGER",
    }
    root = tmp_path / safe_name(spec["run_id"]) / safe_name(spec["case_id"])
    (root / "generation").mkdir(parents=True)
    (root / "generation/trajectory.jsonl").write_text("", encoding="utf-8")
    manifest = {
        "solver": {
            "generation_completed": True,
            "metadata": {
                "image_digest": "sha256:image",
                "goal_contract": {"sha256": "goal"},
                "repository_integrity": {"valid": True},
            },
        },
        "result": {
            "evaluation_completed": False,
            "official_pass": False,
            "metadata": {
                "adapter_error": (
                    "FileNotFoundError: [Errno 2] "
                    "No such file or directory: 'uv'"
                )
            },
        },
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = _episode(tmp_path, spec)

    assert result["censored"] is True
    assert "official-evaluation-incomplete" in result["validity_errors"]
    assert (
        "official-infrastructure:evaluator-host-missing-uv"
        in result["validity_errors"]
    )
    assert result["official_evaluation"]["original_infrastructure_signature"] == (
        "evaluator-host-missing-uv"
    )


def test_cross_arm_validity_censors_both_records_on_identity_mismatch() -> None:
    records = [
        {
            "pair_id": "pair-1",
            "censored": False,
            "validity_errors": [],
            "execution_identity": {
                "image_digest": digest,
                "goal_contract_sha256": "goal",
            },
        }
        for digest in ("sha256:a", "sha256:b")
    ]

    _apply_cross_arm_validity(records)

    assert all(item["censored"] for item in records)
    assert all(
        item["validity_errors"] == ["cross-arm-image-digest-mismatch"]
        for item in records
    )


def test_cross_arm_validity_accepts_matching_execution_identity() -> None:
    records = [
        {
            "pair_id": "pair-1",
            "censored": False,
            "validity_errors": [],
            "execution_identity": {
                "image_digest": "sha256:image",
                "goal_contract_sha256": "goal",
            },
        }
        for _ in range(2)
    ]

    _apply_cross_arm_validity(records)

    assert not any(item["censored"] for item in records)
    assert not any(item["validity_errors"] for item in records)


def test_replacement_schedules_target_declared_original_positions(
    tmp_path: Path,
) -> None:
    episodes = [
        {"position": position, "run_id": f"original-{position}"}
        for position in range(1, 4)
    ]
    paths = []
    for position in (1, 3):
        path = tmp_path / f"replacement-{position}.json"
        path.write_text(
            json.dumps(
                {
                    "episodes": [
                        {
                            "position": 1,
                            "original_position": position,
                            "run_id": f"replacement-{position}",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        paths.append(path)

    result = _apply_replacement_schedules(episodes, paths)

    assert [item["run_id"] for item in result] == [
        "replacement-1",
        "original-2",
        "replacement-3",
    ]


def test_replacement_schedules_reject_duplicate_original_positions(
    tmp_path: Path,
) -> None:
    episodes = [{"position": 1, "run_id": "original-1"}]
    paths = []
    for index in range(2):
        path = tmp_path / f"replacement-{index}.json"
        path.write_text(
            json.dumps(
                {
                    "episodes": [
                        {
                            "position": 1,
                            "original_position": 1,
                            "run_id": f"replacement-{index}",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        paths.append(path)

    try:
        _apply_replacement_schedules(episodes, paths)
    except ValueError as error:
        assert str(error) == "Duplicate replacement for position 1"
    else:
        raise AssertionError("duplicate replacement was accepted")


def test_candidate_boundary_requires_a_hash_matched_certificate() -> None:
    events = [
        {
            "event": "tool_result",
            "tool_name": "submit_and_replay",
            "request_index": 2,
            "result": {
                "status": "pass",
                "program_sha256": "candidate",
                "certificate": {"program_sha256": "different"},
            },
        },
        {
            "event": "tool_result",
            "tool_name": "submit_and_replay",
            "request_index": 4,
            "result": {
                "status": "pass",
                "program_sha256": "candidate",
                "certificate": {"program_sha256": "candidate"},
            },
        },
    ]

    assert _candidate_event(events) is events[1]


def test_usage_stops_at_the_frozen_candidate_boundary() -> None:
    events = [
        {
            "event": "provider_response",
            "request_index": index,
            "response": {
                "usage": {
                    "prompt_tokens": 10 * index,
                    "completion_tokens": index,
                    "total_tokens": 11 * index,
                    "cost": 0.1 * index,
                    "completion_tokens_details": {"reasoning_tokens": index - 1},
                }
            },
        }
        for index in (1, 2, 3)
    ]

    assert _usage(events, 2) == {
        "model_requests": 2,
        "prompt_tokens": 30,
        "completion_tokens": 3,
        "reasoning_tokens": 1,
        "total_tokens": 33,
        "cost": 0.30000000000000004,
    }


def test_terminal_provider_failure_requires_no_later_success() -> None:
    failure = {
        "event": "provider_error",
        "request_index": 3,
        "next_retry_delay_seconds": None,
    }
    assert _terminal_provider_failure([failure]) is True
    assert (
        _terminal_provider_failure(
            [failure, {"event": "provider_response", "request_index": 3}]
        )
        is False
    )


def _record(pair: int, arm: str) -> dict[str, object]:
    treatment = arm == "D-LEDGER"
    value = 8 if treatment else 10
    return {
        "pair_id": f"pair-{pair}",
        "arm": arm,
        "censored": False,
        "candidate_formed": True,
        "official_pass": True,
        "pre_candidate": {
            "model_requests": value,
            "interactive_tool_steps": value,
            "total_tokens": value * 100,
            "seconds_to_certificate": value * 10,
        },
        "mechanism": {
            "check_count": 1 if treatment else 0,
            "complete_check_count": 1 if treatment else 0,
            "operation_constraint_violations": 0,
            "ledger_metadata": (
                {
                    "transition_counts": {"initial": 1, "improved": 1},
                    "stores_container_checkpoint": False,
                }
                if treatment
                else {}
            ),
        },
    }


def test_adjudication_applies_the_preregistered_efficiency_rule() -> None:
    records = [
        _record(pair, arm)
        for pair in range(4)
        for arm in ("B-FSR", "D-LEDGER")
    ]
    pairs = _pairs(records)  # type: ignore[arg-type]
    result = _adjudicate(records, pairs)  # type: ignore[arg-type]

    assert result["mechanism_acceptance"]["passed"] is True
    assert result["directional"]["efficiency_signal"] is True
    assert result["decision"] == (
        "positive-directional-promote-to-broader-consumed-study"
    )


def test_adjudication_rejects_lower_treatment_success_count() -> None:
    records = [
        _record(pair, arm)
        for pair in range(4)
        for arm in ("B-FSR", "D-LEDGER")
    ]
    treatment = next(
        item
        for item in records
        if item["pair_id"] == "pair-0" and item["arm"] == "D-LEDGER"
    )
    treatment["candidate_formed"] = False
    treatment["official_pass"] = False
    pairs = _pairs(records)  # type: ignore[arg-type]
    result = _adjudicate(records, pairs)  # type: ignore[arg-type]

    assert result["decision"] == "negative-directional-do-not-expose-frozen-dev"
