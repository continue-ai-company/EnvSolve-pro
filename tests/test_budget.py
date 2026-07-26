from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from envsolve_harness.budget import (
    BudgetExceeded,
    BudgetLedger,
    BudgetLimits,
    TokenPricing,
    UsageDelta,
    budget_ledger_from_environment,
)
from envsolve.solver import EpisodeBudgetExhausted
from envsolve_harness.core.io import read_json
from unittest import mock


class BudgetLedgerTest(unittest.TestCase):
    def test_budget_exceeded_implements_solver_terminal_protocol(self) -> None:
        error = BudgetExceeded("environments", {"usage": {}})

        self.assertIsInstance(error, EpisodeBudgetExhausted)
        self.assertEqual(error.scope, "environments")
        self.assertEqual(error.snapshot, {"usage": {}})
        self.assertEqual(str(error), "Online model budget exhausted: environments")

    def make_ledger(
        self,
        root: Path,
        *,
        requests: int = 2,
        tokens: int = 100,
        cost: float = 1.0,
    ) -> BudgetLedger:
        return BudgetLedger(
            root / "ledger.json",
            BudgetLimits(requests, tokens, cost),
            TokenPricing("test/model", 1.0, 2.0, 0.1, "https://example.test", "2026-01-01"),
        )

    def test_request_budget_blocks_before_the_next_model_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = self.make_ledger(root, requests=2, tokens=1_000_000)
            ledger.preflight()
            ledger.record_response(UsageDelta(10, 2))
            ledger.preflight()
            ledger.record_response(UsageDelta(10, 2))
            with self.assertRaises(BudgetExceeded) as raised:
                ledger.preflight()
            self.assertEqual(raised.exception.scope, "model_requests")
            persisted = read_json(root / "ledger.json")
            self.assertEqual(persisted["usage"]["requests_started"], 2)
            self.assertEqual(persisted["termination"]["kind"], "budget_exhausted")

    def test_token_budget_is_accounted_after_response_and_blocks_next_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = self.make_ledger(Path(directory), requests=10, tokens=100)
            ledger.preflight()
            snapshot = ledger.record_response(UsageDelta(60, 40, 20))
            self.assertEqual(snapshot["usage"]["total_tokens"], 100)
            self.assertEqual(snapshot["exhausted_limits"], ["total_tokens"])
            with self.assertRaises(BudgetExceeded) as raised:
                ledger.preflight()
            self.assertEqual(raised.exception.scope, "total_tokens")

    def test_estimated_cost_uses_frozen_cache_input_and_output_prices(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = self.make_ledger(
                Path(directory), requests=10, tokens=1_000_000, cost=0.0000095
            )
            ledger.preflight()
            snapshot = ledger.record_response(UsageDelta(10, 2, 5))
            self.assertAlmostEqual(snapshot["usage"]["estimated_cost_usd"], 0.0000095)
            with self.assertRaises(BudgetExceeded) as raised:
                ledger.preflight()
            self.assertEqual(raised.exception.scope, "estimated_cost_usd")

    def test_environment_bridge_constructs_the_same_generic_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            "os.environ",
            {
                "ENVSOLVE_BUDGET_LEDGER_PATH": str(Path(directory) / "ledger.json"),
                "ENVSOLVE_BUDGET_MAX_MODEL_REQUESTS": "3",
                "ENVSOLVE_BUDGET_MAX_TOTAL_TOKENS": "400",
                "ENVSOLVE_BUDGET_MAX_ESTIMATED_COST_USD": "2.5",
                "ENVSOLVE_BUDGET_MODEL": "test/model",
                "ENVSOLVE_BUDGET_INPUT_COST_PER_MILLION": "1.0",
                "ENVSOLVE_BUDGET_OUTPUT_COST_PER_MILLION": "2.0",
            },
            clear=False,
        ):
            ledger = budget_ledger_from_environment()
            self.assertIsNotNone(ledger)
            assert ledger is not None
            ledger.preflight()
            snapshot = ledger.record_response(UsageDelta(20, 5))
            self.assertEqual(snapshot["limits"]["max_model_requests"], 3)
            self.assertEqual(snapshot["usage"]["total_tokens"], 25)

    def test_episode_resources_share_one_resumable_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            limits = BudgetLimits(
                10,
                1_000_000,
                5.0,
                max_candidates=2,
                max_environments=2,
                max_commands=2,
                max_wall_clock_seconds=60,
            )
            pricing = TokenPricing("test/model", 1.0, 2.0)
            first = BudgetLedger(root / "ledger.json", limits, pricing)
            first.preflight()
            first.record_response(UsageDelta(10, 2))
            first.reserve_candidate("candidate-1")
            first.reserve_environment("candidate-1")
            first.reserve_command("candidate-1")

            resumed = BudgetLedger(root / "ledger.json", limits, pricing)
            snapshot = resumed.snapshot()
            self.assertEqual(snapshot["usage"]["requests_started"], 1)
            self.assertEqual(snapshot["usage"]["candidates"], 1)
            resumed.reserve_candidate("candidate-2")
            with self.assertRaises(BudgetExceeded) as raised:
                resumed.reserve_candidate("candidate-3")
            self.assertEqual(raised.exception.scope, "candidates")

    def test_precreated_instances_merge_serial_model_and_execution_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            limits = BudgetLimits(
                10,
                1_000_000,
                5.0,
                max_candidates=2,
                max_environments=2,
                max_commands=2,
            )
            pricing = TokenPricing("test/model", 1.0, 2.0)
            model_ledger = BudgetLedger(root / "ledger.json", limits, pricing)
            episode_ledger = BudgetLedger(root / "ledger.json", limits, pricing)

            model_ledger.preflight()
            model_ledger.record_response(UsageDelta(100, 20))
            episode_ledger.reserve_candidate("candidate-1")
            episode_ledger.reserve_environment("candidate-1")
            episode_ledger.reserve_command("candidate-1")

            snapshot = model_ledger.snapshot()
            self.assertEqual(snapshot["usage"]["requests_started"], 1)
            self.assertEqual(snapshot["usage"]["total_tokens"], 120)
            self.assertEqual(snapshot["usage"]["candidates"], 1)
            self.assertEqual(snapshot["usage"]["environments"], 1)
            self.assertEqual(snapshot["usage"]["commands"], 1)

    def test_in_progress_provider_attempt_survives_ledger_resume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self.make_ledger(
                root,
                requests=10,
                tokens=1_000_000,
            )
            first.preflight()
            first.record_provider_attempt_start("attempt-1")

            resumed = self.make_ledger(
                root,
                requests=10,
                tokens=1_000_000,
            )
            snapshot = resumed.snapshot()

            self.assertEqual(snapshot["schema_version"], "1.1.0")
            self.assertEqual(snapshot["usage"]["requests_started"], 1)
            self.assertEqual(
                snapshot["provider_attempts"],
                [
                    {
                        "attempt_id": "attempt-1",
                        "started_at": snapshot["provider_attempts"][0]["started_at"],
                        "finished_at": None,
                        "duration_seconds": None,
                        "outcome": "in_progress",
                    }
                ],
            )

    def test_finalize_persists_terminal_wall_time_and_closes_the_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            limits = BudgetLimits(
                10,
                1_000_000,
                5.0,
                max_candidates=2,
                max_environments=2,
                max_commands=2,
                max_wall_clock_seconds=60,
            )
            ledger = BudgetLedger(
                root / "ledger.json",
                limits,
                TokenPricing("test/model", 1.0, 2.0),
            )
            ledger.reserve_candidate("candidate-1")
            with mock.patch.object(ledger, "_elapsed_seconds", return_value=61.0):
                finalized = ledger.finalize()

            self.assertEqual(finalized["usage"]["elapsed_wall_clock_seconds"], 61.0)
            self.assertEqual(finalized["exhausted_limits"], ["wall_clock_seconds"])
            self.assertIsInstance(finalized["finalized_at"], str)
            self.assertEqual(read_json(root / "ledger.json"), finalized)
            with self.assertRaisesRegex(RuntimeError, "finalized"):
                ledger.reserve_candidate("candidate-2")


if __name__ == "__main__":
    unittest.main()
