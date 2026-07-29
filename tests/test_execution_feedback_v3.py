from envsolve.runtime.execution_feedback import (
    EXECUTION_FEEDBACK_CHECK_PROFILE,
    recover_goal_execution_failure,
)
from envsolve.solver import (
    CommandResult,
    DeploymentCandidate,
    ExecutableVerification,
    FeedbackChannel,
)
from envsolve_harness.scripts.observable_open_program import (
    OBSERVABLE_OPEN_PROGRAM_POLICY,
    ObservableOpenCandidateProgramValidator,
)


def _unknown_goal_report(stderr: str) -> ExecutableVerification:
    return ExecutableVerification(
        verifier="envsolve-executable-goal-verifier",
        check_profile="executable-goal-contract-v2",
        channel=FeedbackChannel.INTERNAL_EXECUTION,
        passed=None,
        bootstrap=CommandResult(1, stderr=stderr),
        summary="Executable goal did not produce a valid report",
        details={
            "goal_exit_code": 1,
            "report_observed": False,
        },
    )


def test_observable_validator_preserves_mutation_diagnostics() -> None:
    validator = ObservableOpenCandidateProgramValidator()
    result = validator.validate(
        DeploymentCandidate(
            "candidate-0001",
            (
                "command -v jq >/dev/null 2>&1 || true\n"
                "python -m pip install -e . >/dev/null 2>&1\n"
                "make &>/dev/null\n"
            ),
            "Install the project.",
        )
    )

    assert result.accepted is True
    assert result.policy_id == OBSERVABLE_OPEN_PROGRAM_POLICY
    assert "command -v jq >/dev/null 2>&1" in str(result.normalized_script)
    assert "python -m pip install -e . 2>&1\n" in str(
        result.normalized_script
    )
    assert "make\n" in str(result.normalized_script)
    assert result.details["diagnostic_redirection_removal_count"] == 2


def test_goal_process_failure_becomes_recoverable_feedback() -> None:
    recovered = recover_goal_execution_failure(
        _unknown_goal_report("ModuleNotFoundError: No module named 'distutils'")
    )

    assert recovered.passed is False
    assert recovered.check_profile == EXECUTION_FEEDBACK_CHECK_PROFILE
    assert recovered.details["recoverable_goal_execution_failure"] is True
    assert recovered.hypotheses[0].hypothesis_id == (
        "hypothesis-goal-execution-state-conflict"
    )


def test_network_goal_process_failure_remains_censored_unknown() -> None:
    recovered = recover_goal_execution_failure(
        _unknown_goal_report("ProxyError: connection reset by peer")
    )

    assert recovered.passed is None
    assert recovered.details["failure_disposition"] == "infrastructure-censored"
