from experiments.analyze_for_mechanism import analyze


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
) -> dict:
    resources = None if tokens is None else {
        "requests_started": tokens // 10,
        "total_tokens": tokens,
        "elapsed_wall_clock_seconds": tokens / 2,
        "commands": tokens // 20,
    }
    return {
        "pair_id": pair_id,
        "method": METHODS[arm],
        "scientifically_eligible": eligible,
        "official_pass": passed,
        "descriptive_terminal": (
            "official_pass" if passed else "official_fail" if passed is False else "incomplete"
        ),
        "resources": resources,
    }


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
