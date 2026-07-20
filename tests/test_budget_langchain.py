from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import tempfile
import unittest

from envsolve_harness.budget.langchain import OnlineBudgetCallback
from envsolve_harness.core.io import read_json


class BudgetLangChainCallbackTest(unittest.TestCase):
    def _callback(self, ledger: Path) -> OnlineBudgetCallback:
        return OnlineBudgetCallback(
            ledger_path=str(ledger),
            max_model_requests=5,
            max_total_tokens=100_000,
            max_estimated_cost_usd=10.0,
            model="provider/model",
            input_cost_per_million=1.0,
            output_cost_per_million=2.0,
        )

    def test_length_finished_response_records_usage_instead_of_request_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.json"
            callback = self._callback(ledger)
            run_id = uuid4()
            callback.on_chat_model_start({}, [[]], run_id=run_id)
            error = Exception("length")
            error.completion = SimpleNamespace(
                usage=SimpleNamespace(
                    prompt_tokens=2878,
                    completion_tokens=16384,
                    prompt_tokens_details=SimpleNamespace(cached_tokens=128),
                )
            )

            callback.on_llm_error(error, run_id=run_id)

            usage = read_json(ledger)["usage"]
            self.assertEqual(usage["requests_started"], 1)
            self.assertEqual(usage["responses_completed"], 1)
            self.assertEqual(usage["request_errors"], 0)
            self.assertEqual(usage["input_tokens"], 2878)
            self.assertEqual(usage["output_tokens"], 16384)
            self.assertEqual(usage["cache_read_tokens"], 128)

    def test_transport_error_remains_a_request_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.json"
            callback = self._callback(ledger)
            run_id = uuid4()
            callback.on_chat_model_start({}, [[]], run_id=run_id)

            callback.on_llm_error(RuntimeError("connection lost"), run_id=run_id)

            usage = read_json(ledger)["usage"]
            self.assertEqual(usage["responses_completed"], 0)
            self.assertEqual(usage["request_errors"], 1)


if __name__ == "__main__":
    unittest.main()
