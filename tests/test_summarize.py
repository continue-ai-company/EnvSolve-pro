from __future__ import annotations

import unittest

from experiments.summarize_run import _failure_stage, _model_usage


class ModelUsageSummaryTest(unittest.TestCase):
    def test_online_budget_usage_is_used_even_when_generation_fails(self) -> None:
        usage = _model_usage(
            {
                "online_budget": {
                    "usage": {
                        "requests_started": 4,
                        "responses_completed": 3,
                        "request_errors": 1,
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "cache_read_tokens": 80,
                        "total_tokens": 120,
                        "estimated_cost_usd": 0.25,
                    }
                },
                "token_usage": {"requests": 999, "total_tokens": 999},
            }
        )

        self.assertEqual(usage["model_requests"], 4)
        self.assertEqual(usage["model_responses"], 3)
        self.assertEqual(usage["model_request_errors"], 1)
        self.assertEqual(usage["cache_read_tokens"], 80)
        self.assertEqual(usage["total_tokens"], 120)
        self.assertEqual(usage["estimated_cost_usd"], 0.25)

    def test_legacy_trajectory_usage_remains_supported(self) -> None:
        usage = _model_usage(
            {
                "token_usage": {
                    "requests": 2,
                    "input_tokens": 40,
                    "output_tokens": 5,
                    "total_tokens": 45,
                }
            }
        )

        self.assertEqual(usage["model_requests"], 2)
        self.assertEqual(usage["total_tokens"], 45)
        self.assertIsNone(usage["estimated_cost_usd"])


class FailureStageSummaryTest(unittest.TestCase):
    def _record(self, **overrides: object) -> dict[str, object]:
        record: dict[str, object] = {
            "generation_completed": True,
            "evaluation_completed": True,
            "official_pass": False,
            "raw_metrics": {"exit_code": 0},
            "diagnostic_evidence": [],
        }
        record.update(overrides)
        return record

    def test_failure_stages_follow_the_frozen_baseline_contract(self) -> None:
        cases = (
            (self._record(generation_completed=False), "generation"),
            (self._record(evaluation_completed=False), "evaluator"),
            (
                self._record(
                    diagnostic_evidence=[
                        {
                            "verifier_id": "envbench-bootstrap-diagnostic",
                            "passed": False,
                        }
                    ]
                ),
                "bootstrap",
            ),
            (self._record(raw_metrics={"exit_code": 1}), "bootstrap"),
            (self._record(), "verification"),
            (self._record(official_pass=True), "success"),
        )
        for record, expected in cases:
            with self.subTest(expected=expected, record=record):
                self.assertEqual(_failure_stage(record), expected)


if __name__ == "__main__":
    unittest.main()
