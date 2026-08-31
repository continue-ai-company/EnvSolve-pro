from envsolve_harness.constraint_hypothesis import evaluate_constraint_hypothesis


TARGET = {
    "domain": "python-import",
    "subject": "scanpy",
    "predicate": "importable",
    "required": True,
}
OTHER = {
    "domain": "python-import",
    "subject": "numpy",
    "predicate": "importable",
    "required": True,
}


def observation(*obligations: dict[str, object]) -> dict[str, object]:
    return {
        "ok": True,
        "goal_status": "pass" if not obligations else "fail",
        "candidate_ready": not obligations,
        "current": {"obligations": list(obligations)},
    }


def evaluate(after: dict[str, object]) -> dict[str, object]:
    return evaluate_constraint_hypothesis(
        provider={"kind": "installed-distribution", "identity": "scanpy"},
        expected_effect="make scanpy importable",
        target_obligations=[TARGET],
        operation={"exit_code": 0},
        before=observation(TARGET),
        after=after,
    )


def test_support_requires_exact_target_resolution_without_regression() -> None:
    result = evaluate(observation())

    assert result["classification"] == "supported"
    assert result["effect_evidence"]["resolved_target_count"] == 1
    assert result["hypothesis"]["provider_identity_evidence"] == (
        "agent-declared-not-independently-verified"
    )
    assert result["operation_constraints_added"] is False


def test_partial_support_records_new_obligations() -> None:
    result = evaluate(observation(OTHER))

    assert result["classification"] == "partially_supported"
    assert result["effect_evidence"]["introduced_obligation_count"] == 1


def test_no_target_resolution_refutes_hypothesis() -> None:
    result = evaluate(observation(TARGET))

    assert result["classification"] == "refuted"


def test_non_active_target_is_invalid_instead_of_claiming_effect() -> None:
    result = evaluate_constraint_hypothesis(
        provider={"kind": "repository-source", "identity": "project"},
        expected_effect="make scanpy importable",
        target_obligations=[TARGET],
        operation={"exit_code": 0},
        before=observation(OTHER),
        after=observation(),
    )

    assert result["classification"] == "invalid_target"
