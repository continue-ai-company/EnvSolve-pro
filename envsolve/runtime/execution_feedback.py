from __future__ import annotations

from dataclasses import replace
import re

from envsolve.runtime.goal_verifier import ExecutableGoalContractVerifier
from envsolve.solver import (
    ExecutableVerification,
    HypothesisEvidence,
    ProvisionedEnvironment,
    DeploymentCandidate,
)


EXECUTION_FEEDBACK_CHECK_PROFILE = "executable-goal-contract-v3-recoverable"
_MISSING_GOAL_REPORT = "Executable goal did not produce a valid report"
_INFRASTRUCTURE_FAILURE = re.compile(
    r"""
    \b(?:
        502\s+Bad\s+Gateway
        |503\s+Service\s+Unavailable
        |504\s+Gateway\s+Time-?out
        |ConnectionError
        |ConnectTimeout
        |ReadTimeout
        |RemoteDisconnected
        |ProxyError
        |Could\s+not\s+resolve\s+host
        |network\s+is\s+unreachable
        |connection\s+reset\s+by\s+peer
        |Temporary\s+failure\s+(?:in\s+name\s+resolution|resolving)
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def recover_goal_execution_failure(
    outcome: ExecutableVerification,
) -> ExecutableVerification:
    """Turn a completed candidate's non-infrastructure goal crash into feedback."""
    if outcome.passed is not None or outcome.summary != _MISSING_GOAL_REPORT:
        return outcome
    if outcome.details.get("report_observed") is not False:
        return outcome
    goal_exit_code = outcome.details.get("goal_exit_code")
    if not isinstance(goal_exit_code, int) or goal_exit_code == 0:
        return outcome
    diagnostic = f"{outcome.bootstrap.stdout}\n{outcome.bootstrap.stderr}"
    if _INFRASTRUCTURE_FAILURE.search(diagnostic):
        return replace(
            outcome,
            check_profile=EXECUTION_FEEDBACK_CHECK_PROFILE,
            details={
                **outcome.details,
                "failure_disposition": "infrastructure-censored",
            },
        )
    return replace(
        outcome,
        check_profile=EXECUTION_FEEDBACK_CHECK_PROFILE,
        passed=False,
        summary=(
            "Candidate completed, but its resulting execution state prevented "
            "the executable goal from producing a report"
        ),
        hypotheses=(
            HypothesisEvidence(
                hypothesis_id="hypothesis-goal-execution-state-conflict",
                statement=(
                    "A candidate-visible environment change may conflict with "
                    "the executable goal process"
                ),
                value={
                    "goal_exit_code": goal_exit_code,
                    "report_observed": False,
                },
                confidence=0.9,
            ),
        ),
        details={
            **outcome.details,
            "failure_disposition": "recoverable-execution-state-conflict",
            "recoverable_goal_execution_failure": True,
            "finding_set_complete": False,
        },
    )


class RecoverableGoalContractVerifier(ExecutableGoalContractVerifier):
    """Preserve infrastructure unknowns and loop on candidate-induced goal crashes."""

    check_profile = EXECUTION_FEEDBACK_CHECK_PROFILE

    def verify(
        self,
        candidate: DeploymentCandidate,
        environment: ProvisionedEnvironment,
    ) -> ExecutableVerification:
        return recover_goal_execution_failure(
            super().verify(candidate, environment)
        )
