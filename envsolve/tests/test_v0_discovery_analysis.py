from __future__ import annotations

import unittest

from envsolve.analysis.discovery import observable_outcome, paired_aggregate


class V0DiscoveryAnalysisTests(unittest.TestCase):
    def test_observable_outcome_does_not_guess_infrastructure(self) -> None:
        solver = {
            "generation_completed": False,
            "error": "request timed out",
            "metadata": {},
        }
        self.assertEqual(observable_outcome(solver, None), "solver_error")

    def test_verifier_rejection_has_an_explicit_boundary(self) -> None:
        solver = {
            "generation_completed": False,
            "error": "last verifier call failed",
            "metadata": {"v0_completion": {"passed": False}},
        }
        self.assertEqual(observable_outcome(solver, None), "verifier_rejection")

    def test_paired_aggregate_counts_directional_wins(self) -> None:
        records = [
            {
                "case_id": "one",
                "condition": "envsolve_v0",
                "observable_outcome": "success",
                "official_pass": True,
            },
            {
                "case_id": "one",
                "condition": "freeagent",
                "observable_outcome": "official_failure",
                "official_pass": False,
            },
        ]
        result = paired_aggregate(records)
        self.assertEqual(result["official_pairing"]["envsolve_v0_only"], 1)

    def test_paired_aggregate_fails_closed_on_missing_condition(self) -> None:
        with self.assertRaisesRegex(ValueError, "incomplete"):
            paired_aggregate(
                [{
                    "case_id": "one",
                    "condition": "envsolve_v0",
                    "observable_outcome": "success",
                    "official_pass": True,
                }]
            )


if __name__ == "__main__":
    unittest.main()
