from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_openai import ChatOpenAI

from envsolve_harness.budget.ledger import BudgetLedger, BudgetLimits, TokenPricing, UsageDelta


def _usage_from_result(result: LLMResult) -> UsageDelta:
    llm_output = result.llm_output if isinstance(result.llm_output, dict) else {}
    token_usage = llm_output.get("token_usage")
    if isinstance(token_usage, dict):
        input_tokens = int(
            token_usage.get("prompt_tokens", token_usage.get("input_tokens", 0)) or 0
        )
        output_tokens = int(
            token_usage.get("completion_tokens", token_usage.get("output_tokens", 0)) or 0
        )
        details = token_usage.get("prompt_tokens_details") or token_usage.get(
            "input_token_details"
        )
        cache_read = int(
            (
                details.get("cached_tokens", details.get("cache_read", 0))
                if isinstance(details, dict)
                else 0
            )
            or 0
        )
        if input_tokens or output_tokens:
            return UsageDelta(input_tokens, output_tokens, min(cache_read, input_tokens))

    input_tokens = 0
    output_tokens = 0
    cache_read = 0
    for generation_group in result.generations:
        for generation in generation_group:
            message = getattr(generation, "message", None)
            usage = getattr(message, "usage_metadata", None)
            if not isinstance(usage, dict):
                continue
            input_tokens += int(usage.get("input_tokens", 0) or 0)
            output_tokens += int(usage.get("output_tokens", 0) or 0)
            details = usage.get("input_token_details")
            if isinstance(details, dict):
                cache_read += int(details.get("cache_read", 0) or 0)
    return UsageDelta(input_tokens, output_tokens, min(cache_read, input_tokens))


class OnlineBudgetCallback(BaseCallbackHandler):
    raise_error = True

    def __init__(
        self,
        ledger_path: str,
        max_model_requests: int,
        max_total_tokens: int,
        max_estimated_cost_usd: float,
        model: str,
        input_cost_per_million: float,
        output_cost_per_million: float,
        cache_read_cost_per_million: float | None = None,
        pricing_source_url: str | None = None,
        pricing_snapshot_date: str | None = None,
        max_candidates: int | None = None,
        max_environments: int | None = None,
        max_commands: int | None = None,
        max_wall_clock_seconds: int | None = None,
    ) -> None:
        self.ledger = BudgetLedger(
            Path(ledger_path),
            BudgetLimits(
                max_model_requests,
                max_total_tokens,
                max_estimated_cost_usd,
                max_candidates=max_candidates,
                max_environments=max_environments,
                max_commands=max_commands,
                max_wall_clock_seconds=max_wall_clock_seconds,
            ),
            TokenPricing(
                model=model,
                input_cost_per_million=input_cost_per_million,
                output_cost_per_million=output_cost_per_million,
                cache_read_cost_per_million=cache_read_cost_per_million,
                source_url=pricing_source_url,
                snapshot_date=pricing_snapshot_date,
            ),
        )

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self.ledger.preflight()

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        self.ledger.record_response(_usage_from_result(response))

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self.ledger.record_error()


def create_budgeted_chat_model(
    *,
    model: str,
    budget_ledger_path: str,
    budget_max_model_requests: int,
    budget_max_total_tokens: int,
    budget_max_estimated_cost_usd: float,
    budget_input_cost_per_million: float,
    budget_output_cost_per_million: float,
    budget_cache_read_cost_per_million: float | None = None,
    budget_pricing_source_url: str | None = None,
    budget_pricing_snapshot_date: str | None = None,
    budget_max_candidates: int | None = None,
    budget_max_environments: int | None = None,
    budget_max_commands: int | None = None,
    budget_max_wall_clock_seconds: int | None = None,
    callbacks: list[Any] | None = None,
    **model_kwargs: Any,
) -> ChatOpenAI:
    callback = OnlineBudgetCallback(
        ledger_path=budget_ledger_path,
        max_model_requests=budget_max_model_requests,
        max_total_tokens=budget_max_total_tokens,
        max_estimated_cost_usd=budget_max_estimated_cost_usd,
        model=model,
        input_cost_per_million=budget_input_cost_per_million,
        output_cost_per_million=budget_output_cost_per_million,
        cache_read_cost_per_million=budget_cache_read_cost_per_million,
        pricing_source_url=budget_pricing_source_url,
        pricing_snapshot_date=budget_pricing_snapshot_date,
        max_candidates=budget_max_candidates,
        max_environments=budget_max_environments,
        max_commands=budget_max_commands,
        max_wall_clock_seconds=budget_max_wall_clock_seconds,
    )
    return ChatOpenAI(model=model, callbacks=[*(callbacks or []), callback], **model_kwargs)
