from __future__ import annotations

import unittest

from envsolve.controller.outcomes import ReplayObservation, ReplayOutcome, ReplayOutcomePolicy


class ReplayOutcomePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ReplayOutcomePolicy()

    def test_official_pass_requires_completed_verifier(self) -> None:
        outcome = self.policy.classify(ReplayObservation(0, 0, True, ""))
        self.assertEqual(outcome, ReplayOutcome.OFFICIAL_PASS)

    def test_open_verifier_findings_preserve_bootstrap_success(self) -> None:
        outcome = self.policy.classify(ReplayObservation(0, 3, True, ""))
        self.assertEqual(outcome, ReplayOutcome.BOOTSTRAP_SATISFIED_VERIFIER_OPEN)

    def test_network_signature_without_verifier_is_infrastructure(self) -> None:
        outcome = self.policy.classify(
            ReplayObservation(2, 0, False, "files.pythonhosted.org: ReadTimeoutError")
        )
        self.assertEqual(outcome, ReplayOutcome.INFRASTRUCTURE_BLOCKED)

    def test_network_text_cannot_override_completed_semantic_failure(self) -> None:
        outcome = self.policy.classify(
            ReplayObservation(1, 0, True, "old log contained ReadTimeoutError")
        )
        self.assertEqual(outcome, ReplayOutcome.BOOTSTRAP_CONFLICT)

    def test_nonzero_without_network_evidence_is_bootstrap_conflict(self) -> None:
        outcome = self.policy.classify(ReplayObservation(1, 0, False, "resolution impossible"))
        self.assertEqual(outcome, ReplayOutcome.BOOTSTRAP_CONFLICT)

