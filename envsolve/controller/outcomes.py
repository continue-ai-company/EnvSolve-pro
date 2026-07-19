from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


class ReplayOutcome(str, Enum):
    OFFICIAL_PASS = "official_pass"
    BOOTSTRAP_SATISFIED_VERIFIER_OPEN = "bootstrap_satisfied_verifier_open"
    INFRASTRUCTURE_BLOCKED = "infrastructure_blocked"
    BOOTSTRAP_CONFLICT = "bootstrap_conflict"


@dataclass(frozen=True)
class ReplayObservation:
    exit_code: int
    issues_count: int
    verifier_completed: bool
    logs: str


_NETWORK_FAILURES = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ReadTimeoutError",
        r"ConnectionError",
        r"Temporary failure in name resolution",
        r"Could not resolve host",
        r"TLSV?\s+handshake.*timed out",
        r"network is unreachable",
    )
)


class ReplayOutcomePolicy:
    def classify(self, observation: ReplayObservation) -> ReplayOutcome:
        if observation.exit_code == 0 and observation.verifier_completed:
            if observation.issues_count == 0:
                return ReplayOutcome.OFFICIAL_PASS
            return ReplayOutcome.BOOTSTRAP_SATISFIED_VERIFIER_OPEN
        if not observation.verifier_completed and any(
            pattern.search(observation.logs) for pattern in _NETWORK_FAILURES
        ):
            return ReplayOutcome.INFRASTRUCTURE_BLOCKED
        return ReplayOutcome.BOOTSTRAP_CONFLICT

