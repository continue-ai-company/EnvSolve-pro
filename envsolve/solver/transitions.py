from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from envsolve.solver.counterexample import ExecutableVerification


class StateTransitionDisposition(str, Enum):
    REUSABLE = "reusable"
    DAMAGED = "damaged"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class StateTransitionAssessment:
    disposition: StateTransitionDisposition
    reason: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["disposition"] = self.disposition.value
        return value


def _integrity_invalid(outcome: ExecutableVerification) -> bool:
    if any(
        item.kind == "candidate-integrity-observation"
        and isinstance(item.value, dict)
        and item.value.get("integrity_valid") is False
        for item in outcome.observations
    ):
        return True
    return any(
        marker in outcome.summary.lower()
        for marker in (
            "effect boundaries",
            "protected environment",
            "outer workspace",
            "synthetic python import alias",
        )
    )


def assess_state_transition(
    outcome: ExecutableVerification,
) -> StateTransitionAssessment:
    """Decide whether a verifier-observed environment may host the next repair."""
    evidence = {
        "verifier": outcome.verifier,
        "check_profile": outcome.check_profile,
        "reported_passed": outcome.passed,
        "bootstrap_exit_code": outcome.bootstrap.exit_code,
        "candidate_assessment": (
            outcome.candidate_assessment.to_dict()
            if outcome.candidate_assessment is not None
            else None
        ),
    }
    if _integrity_invalid(outcome):
        return StateTransitionAssessment(
            StateTransitionDisposition.DAMAGED,
            "verifier observed a violated state-integrity boundary",
            evidence,
        )
    if outcome.passed is None:
        return StateTransitionAssessment(
            StateTransitionDisposition.UNKNOWN,
            "verifier could not complete the state postconditions",
            evidence,
        )
    if outcome.bootstrap.exit_code != 0:
        return StateTransitionAssessment(
            StateTransitionDisposition.UNKNOWN,
            "candidate execution did not complete before state postconditions",
            evidence,
        )
    if outcome.passed is True and not outcome.counterexamples:
        return StateTransitionAssessment(
            StateTransitionDisposition.REUSABLE,
            "candidate and executable goal postconditions passed",
            evidence,
        )
    assessment = outcome.candidate_assessment
    if outcome.passed is False and assessment is not None and assessment.admissible:
        return StateTransitionAssessment(
            StateTransitionDisposition.REUSABLE,
            "candidate completed safely and the executable goal produced complete findings",
            evidence,
        )
    return StateTransitionAssessment(
        StateTransitionDisposition.UNKNOWN,
        "failing verification did not certify a reusable construction state",
        evidence,
    )
