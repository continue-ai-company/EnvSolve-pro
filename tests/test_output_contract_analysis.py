from __future__ import annotations

import unittest

from envsolve_harness.output_contract_analysis import (
    _forbidden_reasoning_paths,
    adjudicate_output_contract,
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

    def test_provider_exception_timing_changes_decision(self) -> None:
        base_counts = {
            "empty_final_failures": 0,
            "budget_as_policy_exception": 0,
            "policy_output_failures": 0,
            "provider_acquisition_failures": 0,
            "length_finish_exceptions": 0,
            "internal_passes": 0,
        }
        usage = {
            "responses_completed": 7,
            "request_errors": 1,
            "response_parse_retries": 0,
            "response_parse_recoveries": 0,
        }

        after = adjudicate_output_contract(
            {**base_counts, "proposals": 7}, usage, []
        )
        before = adjudicate_output_contract(
            {**base_counts, "proposals": 3}, usage, []
        )

        self.assertEqual(
            after["decision"],
            "inconclusive_provider_exception_after_practical_trigger",
        )
        self.assertEqual(before["decision"], "unexercised_provider_exception")

    def test_recovered_provider_parse_error_is_explicitly_qualified(self) -> None:
        adjudication = adjudicate_output_contract(
            {
                "empty_final_failures": 0,
                "budget_as_policy_exception": 0,
                "policy_output_failures": 0,
                "provider_acquisition_failures": 0,
                "length_finish_exceptions": 0,
                "internal_passes": 0,
                "proposals": 6,
            },
            {
                "responses_completed": 6,
                "request_errors": 1,
                "response_parse_retries": 1,
                "response_parse_recoveries": 1,
            },
            [],
        )

        self.assertTrue(adjudication["provider_recovery_qualified"])
        self.assertEqual(
            adjudication["decision"],
            "practical_output_qualified_with_provider_recovery",
        )


if __name__ == "__main__":
    unittest.main()
