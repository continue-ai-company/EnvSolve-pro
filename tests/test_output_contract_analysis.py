from __future__ import annotations

import unittest

from envsolve_harness.output_contract_analysis import (
    _forbidden_reasoning_paths,
    summarize_output_contract_trajectory,
)


class OutputContractTrajectoryTest(unittest.TestCase):
    def test_separates_length_and_budget_policy_exceptions(self) -> None:
        events = [
            {
                "event_type": "failure_recorded",
                "payload": {
                    "category": "candidate-policy-exception",
                    "message": "LengthFinishReasonError: output limit",
                },
            },
            {
                "event_type": "failure_recorded",
                "payload": {
                    "category": "candidate-policy-exception",
                    "message": "BudgetExceeded: Online model budget exhausted: requests",
                },
            },
            {
                "event_type": "failure_recorded",
                "payload": {
                    "category": "candidate-policy-output",
                    "details": {"final_content_empty": True},
                },
            },
        ]

        counts = summarize_output_contract_trajectory(events)["counts"]

        self.assertEqual(counts["policy_exceptions"], 2)
        self.assertEqual(counts["length_finish_exceptions"], 1)
        self.assertEqual(counts["budget_as_policy_exception"], 1)
        self.assertEqual(counts["empty_final_failures"], 1)

    def test_reasoning_audit_allows_metadata_but_rejects_content(self) -> None:
        value = {
            "reasoning_content_present": True,
            "reasoning_tokens": 123,
            "nested": {"reasoning_content": "private chain of thought"},
        }

        self.assertEqual(
            _forbidden_reasoning_paths(value),
            ["$.nested.reasoning_content"],
        )


if __name__ == "__main__":
    unittest.main()
