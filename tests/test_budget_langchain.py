from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import tempfile
import unittest

from langchain_core.runnables import Runnable
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from envsolve_harness.budget.langchain import (
    JSONResponseRetryModel,
    OnlineBudgetCallback,
)
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

    def test_json_response_retry_is_bounded_and_audited(self) -> None:
        class FlakyModel:
            def __init__(self) -> None:
                self.calls = 0

            def invoke(self, input, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise json.JSONDecodeError("bad provider body", "x", 0)
                return "ok"

        with tempfile.TemporaryDirectory() as directory:
            callback = self._callback(Path(directory) / "ledger.json")
            model = FlakyModel()
            retrying = JSONResponseRetryModel(model, callback.ledger, max_retries=2)

            self.assertEqual(retrying.invoke("input"), "ok")

            usage = callback.ledger.snapshot()["usage"]
            self.assertEqual(model.calls, 2)
            self.assertEqual(usage["response_parse_retries"], 1)
            self.assertEqual(usage["response_parse_recoveries"], 1)

    def test_json_response_retry_reports_attempts_when_exhausted(self) -> None:
        class BrokenModel:
            def __init__(self) -> None:
                self.calls = 0

            def invoke(self, input, **kwargs):
                self.calls += 1
                raise json.JSONDecodeError("bad provider body", "x", 0)

        with tempfile.TemporaryDirectory() as directory:
            callback = self._callback(Path(directory) / "ledger.json")
            model = BrokenModel()
            retrying = JSONResponseRetryModel(model, callback.ledger, max_retries=2)

            with self.assertRaises(json.JSONDecodeError) as raised:
                retrying.invoke("input")

            usage = callback.ledger.snapshot()["usage"]
            self.assertEqual(model.calls, 3)
            self.assertEqual(raised.exception.provider_attempts, 3)
            self.assertEqual(usage["response_parse_retries"], 2)
            self.assertEqual(usage["response_parse_recoveries"], 0)

    def test_json_response_retry_supports_async_invocation(self) -> None:
        class FlakyAsyncModel:
            def __init__(self) -> None:
                self.calls = 0

            async def ainvoke(self, input, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise json.JSONDecodeError("bad provider body", "x", 0)
                return "ok"

        with tempfile.TemporaryDirectory() as directory:
            callback = self._callback(Path(directory) / "ledger.json")
            model = FlakyAsyncModel()
            retrying = JSONResponseRetryModel(model, callback.ledger, max_retries=2)

            self.assertEqual(asyncio.run(retrying.ainvoke("input")), "ok")

            usage = callback.ledger.snapshot()["usage"]
            self.assertEqual(model.calls, 2)
            self.assertEqual(usage["response_parse_retries"], 1)
            self.assertEqual(usage["response_parse_recoveries"], 1)

    def test_bind_tools_preserves_runnable_retry_wrapper(self) -> None:
        class ToolBindingModel:
            def __init__(self, bound_tools=None) -> None:
                self.bound_tools = bound_tools

            def bind_tools(self, tools, **kwargs):
                return ToolBindingModel((tools, kwargs))

        with tempfile.TemporaryDirectory() as directory:
            callback = self._callback(Path(directory) / "ledger.json")
            retrying = JSONResponseRetryModel(
                ToolBindingModel(), callback.ledger, max_retries=2
            )

            bound = retrying.bind_tools(["shell"], tool_choice="auto")

            self.assertIsInstance(bound, Runnable)
            self.assertIs(bound.ledger, callback.ledger)
            self.assertEqual(bound.max_retries, 2)
            self.assertEqual(
                bound.model.bound_tools,
                (["shell"], {"tool_choice": "auto"}),
            )

    def test_retry_wrapper_runs_inside_async_react_graph(self) -> None:
        class ReactModel:
            def bind_tools(self, tools, **kwargs):
                return self

            async def ainvoke(self, input, **kwargs):
                return AIMessage(content="done")

            def invoke(self, input, **kwargs):
                return AIMessage(content="done")

        @tool
        def shell(command: str) -> str:
            """Run a shell command."""
            return command

        with tempfile.TemporaryDirectory() as directory:
            callback = self._callback(Path(directory) / "ledger.json")
            retrying = JSONResponseRetryModel(
                ReactModel(), callback.ledger, max_retries=2
            )
            graph = create_react_agent(model=retrying, tools=[shell])

            result = asyncio.run(
                graph.ainvoke({"messages": [HumanMessage(content="finish")]})
            )

            self.assertEqual(result["messages"][-1].content, "done")


if __name__ == "__main__":
    unittest.main()
