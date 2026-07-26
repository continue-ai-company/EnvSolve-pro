from __future__ import annotations

import unittest

from envsolve.solver import (
    CandidateAssessment,
    CommandResult,
    ExecutableVerification,
    FeedbackChannel,
    ObservationEvidence,
    StateTransitionDisposition,
    assess_state_transition,
)


def _outcome(
    *,
    passed: bool | None,
    exit_code: int = 0,
    admissible: bool = False,
    summary: str = "verification",
    observations: tuple[ObservationEvidence, ...] = (),
) -> ExecutableVerification:
    assessment = (
        CandidateAssessment(
            admissible=True,
            unresolved_constraints=1,
            satisfied_constraints=0,
            unknown_constraints=0,
            reason="complete replay with one residual constraint",
        )
        if admissible
        else None
    )
    return ExecutableVerification(
        verifier="test-verifier",
        check_profile="test",
        channel=FeedbackChannel.INTERNAL_EXECUTION,
        passed=passed,
        bootstrap=CommandResult(exit_code),
        summary=summary,
        observations=observations,
        candidate_assessment=assessment,
    )


class StateTransitionAssessmentTests(unittest.TestCase):
    def test_passing_postconditions_are_reusable(self) -> None:
        result = assess_state_transition(_outcome(passed=True))

        self.assertEqual(result.disposition, StateTransitionDisposition.REUSABLE)

    def test_admissible_goal_failure_is_reusable(self) -> None:
        result = assess_state_transition(_outcome(passed=False, admissible=True))

        self.assertEqual(result.disposition, StateTransitionDisposition.REUSABLE)

    def test_timeout_is_unknown_even_if_it_may_have_changed_state(self) -> None:
        result = assess_state_transition(_outcome(passed=None, exit_code=124))

        self.assertEqual(result.disposition, StateTransitionDisposition.UNKNOWN)

    def test_integrity_violation_is_damaged(self) -> None:
        result = assess_state_transition(
            _outcome(
                passed=False,
                summary="Candidate created a synthetic Python import alias",
                observations=(
                    ObservationEvidence(
                        "candidate-integrity-observation",
                        {"integrity_valid": False},
                    ),
                ),
            )
        )

        self.assertEqual(result.disposition, StateTransitionDisposition.DAMAGED)

    def test_unqualified_failure_is_unknown(self) -> None:
        result = assess_state_transition(_outcome(passed=False))

        self.assertEqual(result.disposition, StateTransitionDisposition.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
