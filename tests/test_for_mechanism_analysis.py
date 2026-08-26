import json
from pathlib import Path

import pytest

from experiments.analyze_for_mechanism import (
    _apply_infrastructure_amendment,
    _replay_mechanism,
    _resolve_replacement_schedules,
    analyze,
)


METHODS = {
    "F": "free-feedback-search-repository-signals",
    "F+O": "free-feedback-search-public-goal",
    "F+O+R": "envsolve-pro-fsr-minimal-h",
}


def _run(
    pair_id: str,
    arm: str,
    passed: bool | None,
    *,
    eligible: bool = True,
    tokens: int | None = None,
    replay_mechanism: dict | None = None,
) -> dict:
    resources = None if tokens is None else {
        "requests_started": tokens // 10,
        "total_tokens": tokens,
        "elapsed_wall_clock_seconds": tokens / 2,
        "commands": tokens // 20,
    }
    run = {
        "pair_id": pair_id,
        "method": METHODS[arm],
        "scientifically_eligible": eligible,
        "official_pass": passed,
        "descriptive_terminal": (
            "official_pass" if passed else "official_fail" if passed is False else "incomplete"
        ),
        "resources": resources,
    }
    if replay_mechanism is not None:
        run["replay_mechanism"] = replay_mechanism
    return run


def _summary(runs: list[dict]) -> dict:
    return {
        "schedule": {"path": "schedule.json"},
        "descriptive": {"runs": len(runs)},
        "scientific": {},
        "runs": runs,
    }


def test_separates_public_goal_and_replay_contrasts() -> None:
    runs = [
        _run("case-1", "F", False, tokens=100),
        _run("case-1", "F+O", True, tokens=120),
        _run("case-1", "F+O+R", True, tokens=90),
        _run("case-2", "F", False, tokens=80),
        _run("case-2", "F+O", False, tokens=70),
        _run("case-2", "F+O+R", True, tokens=110),
    ]

    result = analyze(_summary(runs))

    public_goal = result["contrasts"]["public_goal"]["paired_official"]
    replay = result["contrasts"]["target_state_replay"]["paired_official"]
    assert public_goal["treatment_only_pass"] == 1
    assert public_goal["control_only_pass"] == 0
    assert replay["treatment_only_pass"] == 1
    assert replay["both_pass"] == 1


def test_resource_comparison_uses_only_common_success_pairs() -> None:
    runs = [
        _run("case-1", "F", False, tokens=10),
        _run("case-1", "F+O", False, tokens=20),
        _run("case-1", "F+O+R", True, tokens=1000),
        _run("case-2", "F", True, tokens=200),
        _run("case-2", "F+O", True, tokens=150),
        _run("case-2", "F+O+R", True, tokens=120),
    ]

    result = analyze(_summary(runs))

    public_resources = result["contrasts"]["public_goal"][
        "resources_on_common_success"
    ]
    replay_resources = result["contrasts"]["target_state_replay"][
        "resources_on_common_success"
    ]
    assert public_resources["pair_ids"] == ["case-2"]
    assert public_resources["metrics"]["total_tokens"][
        "treatment_minus_control"
    ]["median"] == -50
    assert replay_resources["pair_ids"] == ["case-2"]
    assert replay_resources["metrics"]["total_tokens"][
        "treatment_minus_control"
    ]["median"] == -30


def test_missing_official_result_is_censored_for_primary_but_fails_end_to_end() -> None:
    runs = [
        _run("case-1", "F", None, eligible=True),
        _run("case-1", "F+O", True, eligible=True),
        _run("case-1", "F+O+R", True, eligible=True),
    ]

    result = analyze(_summary(runs))

    contrast = result["contrasts"]["public_goal"]
    assert contrast["paired_official"]["censored_pairs"] == 1
    assert contrast["paired_end_to_end"]["treatment_only_pass"] == 1


def test_extracts_feedback_conditioned_replay_repair(tmp_path) -> None:
    trace = tmp_path / "generation/clean-replay/replays.jsonl"
    trace.parent.mkdir(parents=True)
    trace.write_text(
        "\n".join(
            json.dumps(record)
            for record in (
                {"status": "fail", "program_sha256": "first"},
                {"status": "pass", "program_sha256": "second"},
            )
        )
        + "\n",
        encoding="utf-8",
    )

    mechanism = _replay_mechanism(
        tmp_path,
        replay_exposed=True,
        official_pass=True,
    )

    assert mechanism["statuses"] == ["fail", "pass"]
    assert mechanism["fail_to_pass_repair"] is True
    assert mechanism["program_changed_after_failure"] is True
    assert mechanism["final_replay_official_agreement"] is True


def test_aggregates_replay_activation_and_repair() -> None:
    mechanism = {
        "replay_exposed": True,
        "replay_activated": True,
        "first_replay_certification": False,
        "fail_to_pass_repair": True,
        "program_changed_after_failure": True,
        "final_replay_official_agreement": True,
    }
    runs = [
        _run("case-1", "F", False),
        _run("case-1", "F+O", False),
        _run("case-1", "F+O+R", True, replay_mechanism=mechanism),
    ]

    result = analyze(_summary(runs))

    replay = result["arms"]["F+O+R"]["replay_mechanism"]
    assert replay["activated"] == 1
    assert replay["fail_to_pass_repair"] == 1
    assert replay["program_changed_after_failure"] == 1
    assert replay["replay_official_agreement"] == {"measured": 1, "agrees": 1}


def test_resolves_multi_episode_replacement_to_original_positions() -> None:
    root = Path(__file__).resolve().parents[1]
    schedule, sources = _resolve_replacement_schedules(
        root / "experiments/schedules/envsolve_pro_for_v1_consumed6.json",
        [root / "experiments/schedules/envsolve_pro_for_v1_geoapps_infra_retry2.json"],
    )

    episodes = {episode["position"]: episode for episode in schedule["episodes"]}
    assert episodes[10]["run_id"].endswith("geoapps-F-infra-retry2")
    assert episodes[11]["run_id"].endswith("geoapps-FOR-infra-retry2")
    assert episodes[12]["run_id"].endswith("geoapps-FO-infra-retry2")
    assert sources[0]["original_positions"] == [10, 11, 12]


def test_replacement_rejects_changed_treatment_identity(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    source = json.loads(
        (
            root
            / "experiments/schedules/envsolve_pro_for_v1_geoapps_infra_retry2.json"
        ).read_text(encoding="utf-8")
    )
    source["episodes"][0]["method"] = "changed-method"
    replacement = tmp_path / "replacement.json"
    replacement.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(ValueError, match="Replacement method differs"):
        _resolve_replacement_schedules(
            root / "experiments/schedules/envsolve_pro_for_v1_consumed6.json",
            [replacement],
        )


def test_infrastructure_amendment_censors_source_without_using_retry(
    tmp_path: Path,
) -> None:
    summary = {
        "schedule": {"path": "schedule.json"},
        "descriptive": {},
        "scientific": {},
        "runs": [
            {
                "position": 4,
                "case_id": "owner/repo@abc",
                "run_id": "source-run",
                "artifact_integrity_valid": True,
                "scientifically_eligible": True,
                "eligibility": {
                    "eligible": True,
                    "classification": "scientifically_eligible",
                    "exclusion_reasons": [],
                },
                "descriptive_terminal": "official_fail",
                "official_pass": False,
            }
        ],
    }
    amendment = tmp_path / "amendment.json"
    amendment.write_text(
        json.dumps(
            {
                "official_exact_script_retries": [
                    {
                        "position": 4,
                        "case_id": "owner/repo@abc",
                        "source_run_id": "source-run",
                        "retry_run_id": "retry-run",
                        "infrastructure_signature": "read-timeout",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    _apply_infrastructure_amendment(summary, amendment, tmp_path / "runs")

    run = summary["runs"][0]
    assert run["official_pass"] is None
    assert run["scientifically_eligible"] is False
    assert run["descriptive_terminal"] == "infrastructure_censored"
    assert run["infrastructure_adjudication"]["observed_official_pass"] is False
    assert summary["scientific"]["eligible_runs"] == 0
    assert summary["descriptive"]["official_fail"] == 0
