from __future__ import annotations

import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
import signal
import threading
import time
from typing import Any, Iterator
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APIStatusError, APITimeoutError

from envsolve_harness.budget.ledger import (
    BudgetLedger,
    BudgetLimits,
    TokenPricing,
    UsageDelta,
)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _usage_from_completion(completion: Any) -> UsageDelta | None:
    usage = _field(completion, "usage")
    if usage is None:
        return None
    input_tokens = int(
        _field(usage, "prompt_tokens", _field(usage, "input_tokens", 0)) or 0
    )
    output_tokens = int(
        _field(usage, "completion_tokens", _field(usage, "output_tokens", 0)) or 0
    )
    details = _field(
        usage,
        "prompt_tokens_details",
        _field(usage, "input_token_details"),
    )
    cache_read = int(
        _field(details, "cached_tokens", _field(details, "cache_read", 0)) or 0
    )
    if not input_tokens and not output_tokens:
        return None
    return UsageDelta(input_tokens, output_tokens, min(cache_read, input_tokens))


def _usage_from_error(error: BaseException) -> UsageDelta | None:
    return _usage_from_completion(getattr(error, "completion", None))


def _usage_from_result(result: LLMResult) -> UsageDelta:
    llm_output = result.llm_output if isinstance(result.llm_output, dict) else {}
    token_usage = llm_output.get("token_usage")
    if isinstance(token_usage, dict):
        input_tokens = int(
            token_usage.get("prompt_tokens", token_usage.get("input_tokens", 0)) or 0
        )
        output_tokens = int(
            token_usage.get("completion_tokens", token_usage.get("output_tokens", 0))
            or 0
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
            return UsageDelta(
                input_tokens, output_tokens, min(cache_read, input_tokens)
            )

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


def _provider_error_metadata(error: BaseException) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "error_type": type(error).__name__,
        "error_message": str(error)[:500],
    }
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int):
        metadata["status_code"] = status_code
    request_id = getattr(error, "request_id", None)
    if isinstance(request_id, str) and request_id:
        metadata["provider_request_id"] = request_id
    return metadata


def _retryable_provider_error(error: BaseException) -> str | None:
    if isinstance(error, json.JSONDecodeError):
        return "provider-json-decode"
    if isinstance(error, APITimeoutError | TimeoutError):
        return "provider-timeout"
    if isinstance(error, APIConnectionError | ConnectionError):
        return "provider-connection"
    if isinstance(error, APIStatusError):
        status_code = error.status_code
        if status_code in {408, 409, 429} or status_code >= 500:
            return f"provider-http-{status_code}"
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int) and (
        status_code in {408, 409, 429} or status_code >= 500
    ):
        return f"provider-http-{status_code}"
    return None


@contextmanager
def _synchronous_wall_clock_deadline(
    timeout_seconds: float | None,
) -> Iterator[None]:
    """Interrupt a blocking synchronous provider call at its outer deadline."""

    if timeout_seconds is None:
        yield
        return

    alarm_signal = getattr(signal, "SIGALRM", None)
    timer_kind = getattr(signal, "ITIMER_REAL", None)
    if (
        alarm_signal is None
        or timer_kind is None
        or threading.current_thread() is not threading.main_thread()
    ):
        raise RuntimeError(
            "A hard synchronous provider deadline requires a POSIX main thread; "
            "use ainvoke() in this execution context"
        )

    previous_delay, _ = signal.getitimer(timer_kind)
    if previous_delay > 0:
        raise RuntimeError(
            "Cannot install a hard provider deadline while ITIMER_REAL is active; "
            "use ainvoke() to avoid replacing the existing timer"
        )

    previous_handler = signal.getsignal(alarm_signal)

    def raise_timeout(signum: int, frame: Any) -> None:
        del signum, frame
        raise TimeoutError(
            "Provider request exceeded its hard wall-clock deadline "
            f"({timeout_seconds:.3f}s)"
        )

    signal.signal(alarm_signal, raise_timeout)
    signal.setitimer(timer_kind, max(timeout_seconds, 0.001))
    try:
        yield
    finally:
        signal.setitimer(timer_kind, 0.0)
        signal.signal(alarm_signal, previous_handler)


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
        preflight_on_start: bool = True,
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
        self.preflight_on_start = preflight_on_start

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        if self.preflight_on_start:
            self.ledger.preflight()
        self.ledger.record_provider_attempt_start(str(run_id))

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        self.ledger.record_response(
            _usage_from_result(response),
            provider_attempt_id=str(run_id),
        )

    def on_llm_error(
        self, error: BaseException, *, run_id: UUID, **kwargs: Any
    ) -> None:
        usage = _usage_from_error(error)
        metadata = _provider_error_metadata(error)
        if usage is None:
            self.ledger.record_error(
                provider_attempt_id=str(run_id),
                provider_metadata=metadata,
            )
            return
        self.ledger.record_response(
            usage,
            provider_attempt_id=str(run_id),
            provider_outcome="usage_bearing_error",
            provider_metadata=metadata,
        )


class JSONResponseRetryModel(Runnable[Any, Any]):
    """Expose bounded provider attempts under one logical request deadline."""

    def __init__(
        self,
        model: Any,
        ledger: BudgetLedger,
        max_retries: int,
        request_timeout_seconds: float | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("Provider response retries cannot be negative")
        if request_timeout_seconds is not None and request_timeout_seconds <= 0:
            raise ValueError("Provider request timeout must be positive")
        self.model = model
        self.ledger = ledger
        self.max_retries = max_retries
        self.request_timeout_seconds = request_timeout_seconds

    def _remaining_seconds(self, deadline: float | None) -> float | None:
        if deadline is None:
            return None
        return max(deadline - time.monotonic(), 0.0)

    def _attempt_kwargs(
        self,
        kwargs: dict[str, Any],
        deadline: float | None,
    ) -> dict[str, Any]:
        remaining = self._remaining_seconds(deadline)
        if remaining is None:
            return kwargs
        return {**kwargs, "timeout": max(remaining, 0.001)}

    def _retry_or_raise(
        self,
        error: Exception,
        *,
        attempts: int,
        retries: int,
        deadline: float | None,
    ) -> str:
        setattr(error, "provider_attempts", attempts)
        retry_kind = _retryable_provider_error(error)
        if retry_kind is None or retries >= self.max_retries:
            raise error
        remaining = self._remaining_seconds(deadline)
        if remaining is not None and remaining <= 0:
            setattr(error, "provider_deadline_exhausted", True)
            raise error
        setattr(error, "provider_retry_kind", retry_kind)
        self.ledger.record_provider_retry(retry_kind)
        if isinstance(error, json.JSONDecodeError):
            self.ledger.record_response_parse_retry()
        return retry_kind

    def invoke(
        self,
        input: Any,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> Any:
        self.ledger.preflight()
        deadline = (
            time.monotonic() + self.request_timeout_seconds
            if self.request_timeout_seconds is not None
            else None
        )
        attempts = 0
        retries = 0
        parse_failures = 0
        while True:
            attempts += 1
            try:
                remaining = self._remaining_seconds(deadline)
                with _synchronous_wall_clock_deadline(remaining):
                    response = self.model.invoke(
                        input,
                        config=config,
                        **self._attempt_kwargs(kwargs, deadline),
                    )
            except Exception as exc:
                self._retry_or_raise(
                    exc,
                    attempts=attempts,
                    retries=retries,
                    deadline=deadline,
                )
                retries += 1
                if isinstance(exc, json.JSONDecodeError):
                    parse_failures += 1
                continue
            if parse_failures:
                self.ledger.record_response_parse_recovery()
            if retries:
                self.ledger.record_provider_retry_recovery()
            return response

    async def ainvoke(
        self,
        input: Any,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> Any:
        self.ledger.preflight()
        deadline = (
            time.monotonic() + self.request_timeout_seconds
            if self.request_timeout_seconds is not None
            else None
        )
        attempts = 0
        retries = 0
        parse_failures = 0
        while True:
            attempts += 1
            try:
                attempt = self.model.ainvoke(
                    input,
                    config=config,
                    **self._attempt_kwargs(kwargs, deadline),
                )
                remaining = self._remaining_seconds(deadline)
                response = (
                    await asyncio.wait_for(attempt, timeout=max(remaining, 0.001))
                    if remaining is not None
                    else await attempt
                )
            except Exception as exc:
                self._retry_or_raise(
                    exc,
                    attempts=attempts,
                    retries=retries,
                    deadline=deadline,
                )
                retries += 1
                if isinstance(exc, json.JSONDecodeError):
                    parse_failures += 1
                continue
            if parse_failures:
                self.ledger.record_response_parse_recovery()
            if retries:
                self.ledger.record_provider_retry_recovery()
            return response

    def bind_tools(self, tools: Any, **kwargs: Any) -> "JSONResponseRetryModel":
        return JSONResponseRetryModel(
            self.model.bind_tools(tools, **kwargs),
            self.ledger,
            self.max_retries,
            self.request_timeout_seconds,
        )


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
) -> JSONResponseRetryModel:
    provider_max_retries = int(model_kwargs.get("max_retries", 0) or 0)
    raw_timeout = model_kwargs.get(
        "request_timeout",
        model_kwargs.get("timeout"),
    )
    request_timeout_seconds = (
        float(raw_timeout) if isinstance(raw_timeout, int | float) else None
    )
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
        preflight_on_start=False,
    )
    chat_model = ChatOpenAI(
        model=model,
        callbacks=[*(callbacks or []), callback],
        **{**model_kwargs, "max_retries": 0},
    )
    return JSONResponseRetryModel(
        chat_model,
        callback.ledger,
        provider_max_retries,
        request_timeout_seconds,
    )
