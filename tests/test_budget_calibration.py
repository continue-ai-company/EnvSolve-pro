from __future__ import annotations

import unittest

from envsolve_harness.budget_calibration import summarize_budget_trajectory


class BudgetCalibrationTrajectoryTest(unittest.TestCase):
    def test_counts_executions_recovered_after_old_candidate_cap(self) -> None:
        events = []
        sequence = 0
        exit_codes = (1, 252, 1, 251, 1, 1, 252, 1)
        for index, exit_code in enumerate(exit_codes, start=1):
            candidate_id = f"candidate-{index:04d}"
            events.append(
                {
                    "sequence": sequence,
                    "event_type": "action_proposed",
                    "payload": {"action_id": candidate_id},
                }
            )
            sequence += 1
            events.append(
                {
                    "sequence": sequence,
                    "event_type": "action_finished",
                    "payload": {"action_id": candidate_id, "exit_code": exit_code},
                }
            )
            sequence += 1
        events.extend(
            [
                {
                    "sequence": sequence,
                    "event_type": "failure_recorded",
                    "payload": {
                        "category": "candidate-policy-output",
                        "details": {
                            "response_sha256": (
                                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                            )
                        },
                    },
                },
                {
                    "sequence": sequence + 1,
                    "event_type": "verification_recorded",
                    "payload": {"passed": True},
                },
            ]
        )

        summary = summarize_budget_trajectory(events, old_candidate_cap=5)

        self.assertEqual(summary["counts"]["proposals"], 8)
        self.assertEqual(summary["counts"]["executed"], 5)
        self.assertEqual(summary["counts"]["pre_environment_rejects"], 3)
        self.assertEqual(summary["counts"]["proposals_after_old_cap"], 3)
        self.assertEqual(summary["counts"]["executions_after_old_cap"], 2)
        self.assertEqual(summary["counts"]["empty_policy_responses"], 1)
        self.assertEqual(summary["counts"]["budget_preflight_exceptions"], 0)
        self.assertEqual(summary["counts"]["unexpected_policy_exceptions"], 0)
        self.assertEqual(summary["counts"]["internal_passes"], 1)

    def test_separates_normal_budget_preflight_from_unexpected_exceptions(self) -> None:
        events = [
            {
                "sequence": 1,
                "event_type": "failure_recorded",
                "payload": {
                    "category": "candidate-policy-exception",
                    "message": "BudgetExceeded: Online model budget exhausted: environments",
                },
            },
            {
                "sequence": 2,
                "event_type": "failure_recorded",
                "payload": {
                    "category": "candidate-policy-exception",
                    "message": "JSONDecodeError: malformed provider response",
                },
            },
        ]

        summary = summarize_budget_trajectory(events, old_candidate_cap=5)

        self.assertEqual(summary["counts"]["policy_exceptions"], 2)
        self.assertEqual(summary["counts"]["budget_preflight_exceptions"], 1)
        self.assertEqual(summary["counts"]["unexpected_policy_exceptions"], 1)

    def test_requires_a_finished_transition_for_every_proposal(self) -> None:
        with self.assertRaisesRegex(ValueError, "no finished transition"):
            summarize_budget_trajectory(
                [
                    {
                        "sequence": 1,
                        "event_type": "action_proposed",
                        "payload": {"action_id": "candidate-0001"},
                    }
                ],
                old_candidate_cap=5,
            )


if __name__ == "__main__":
    unittest.main()
