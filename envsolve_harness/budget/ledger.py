from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import threading
from typing import Any

from envsolve_harness.core.io import write_json


@dataclass(frozen=True)
class BudgetLimits:
    max_model_requests: int
    max_total_tokens: int
    max_estimated_cost_usd: float
    max_candidates: int | None = None
    max_environments: int | None = None
    max_commands: int | None = None
    max_wall_clock_seconds: int | None = None

    def __post_init__(self) -> None:
        if self.max_model_requests <= 0 or self.max_total_tokens <= 0:
            raise ValueError("Request and token budgets must be positive")
        if self.max_estimated_cost_usd <= 0:
            raise ValueError("Cost budget must be positive")
        optional = {
            "max_candidates": self.max_candidates,
            "max_environments": self.max_environments,
            "max_commands": self.max_commands,
            "max_wall_clock_seconds": self.max_wall_clock_seconds,
        }
        invalid = {name: value for name, value in optional.items() if value is not None and value <= 0}
        if invalid:
            raise ValueError(f"Execution budgets must be positive: {invalid}")


@dataclass(frozen=True)
class TokenPricing:
    model: str
    input_cost_per_million: float
    output_cost_per_million: float
    cache_read_cost_per_million: float | None = None
    source_url: str | None = None
    snapshot_date: str | None = None

    def __post_init__(self) -> None:
        values = (self.input_cost_per_million, self.output_cost_per_million)
        if any(value < 0 for value in values):
            raise ValueError("Input and output token prices must be non-negative")
        if self.cache_read_cost_per_million is not None and self.cache_read_cost_per_million < 0:
            raise ValueError("Cache-read token price must be non-negative")


@dataclass(frozen=True)
class UsageDelta:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0

    def __post_init__(self) -> None:
        if min(self.input_tokens, self.output_tokens, self.cache_read_tokens) < 0:
            raise ValueError("Token usage cannot be negative")
        if self.cache_read_tokens > self.input_tokens:
            raise ValueError("Cache-read tokens cannot exceed input tokens")

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class BudgetExceeded(RuntimeError):
    def __init__(self, scope: str, snapshot: dict[str, Any]) -> None:
        self.scope = scope
        self.snapshot = snapshot
        super().__init__(f"Online model budget exhausted: {scope}")


class BudgetLedger:
    def __init__(self, path: Path, limits: BudgetLimits, pricing: TokenPricing) -> None:
        self.path = path
        self.limits = limits
        self.pricing = pricing
        self._lock = threading.Lock()
        self._requests_started = 0
        self._responses_completed = 0
        self._request_errors = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._cache_read_tokens = 0
        self._candidates = 0
        self._environments = 0
        self._commands = 0
        self._candidate_ids: list[str] = []
        self._environment_candidate_ids: list[str] = []
        self._command_candidate_ids: list[str] = []
        self._created_at = self._now()
        self._termination: dict[str, Any] | None = None
        self._finalized_at: str | None = None
        if self.path.is_file():
            self._resume_locked()
        else:
            self._write_locked()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _estimated_cost(self) -> Decimal:
        cached = Decimal(self._cache_read_tokens)
        uncached = Decimal(max(self._input_tokens - self._cache_read_tokens, 0))
        output = Decimal(self._output_tokens)
        input_rate = Decimal(str(self.pricing.input_cost_per_million))
        output_rate = Decimal(str(self.pricing.output_cost_per_million))
        cache_rate = Decimal(
            str(
                self.pricing.cache_read_cost_per_million
                if self.pricing.cache_read_cost_per_million is not None
                else self.pricing.input_cost_per_million
            )
        )
        return (uncached * input_rate + cached * cache_rate + output * output_rate) / Decimal(
            1_000_000
        )

    def _exhausted_limits(self) -> tuple[str, ...]:
        exhausted: list[str] = []
        if self._requests_started >= self.limits.max_model_requests:
            exhausted.append("model_requests")
        if self._input_tokens + self._output_tokens >= self.limits.max_total_tokens:
            exhausted.append("total_tokens")
        if self._estimated_cost() >= Decimal(str(self.limits.max_estimated_cost_usd)):
            exhausted.append("estimated_cost_usd")
        if self.limits.max_candidates is not None and self._candidates >= self.limits.max_candidates:
            exhausted.append("candidates")
        if self.limits.max_environments is not None and self._environments >= self.limits.max_environments:
            exhausted.append("environments")
        if self.limits.max_commands is not None and self._commands >= self.limits.max_commands:
            exhausted.append("commands")
        if (
            self.limits.max_wall_clock_seconds is not None
            and self._elapsed_seconds() >= self.limits.max_wall_clock_seconds
        ):
            exhausted.append("wall_clock_seconds")
        return tuple(exhausted)

    def _elapsed_seconds(self) -> float:
        created = datetime.fromisoformat(self._created_at)
        return max((datetime.now(timezone.utc) - created).total_seconds(), 0.0)

    def _limits_dict(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in asdict(self.limits).items()
            if value is not None
        }

    def _snapshot_locked(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "limits": self._limits_dict(),
            "pricing": asdict(self.pricing),
            "usage": {
                "requests_started": self._requests_started,
                "responses_completed": self._responses_completed,
                "request_errors": self._request_errors,
                "input_tokens": self._input_tokens,
                "output_tokens": self._output_tokens,
                "cache_read_tokens": self._cache_read_tokens,
                "total_tokens": self._input_tokens + self._output_tokens,
                "estimated_cost_usd": float(self._estimated_cost()),
                "candidates": self._candidates,
                "environments": self._environments,
                "commands": self._commands,
                "elapsed_wall_clock_seconds": self._elapsed_seconds(),
            },
            "execution_trace": {
                "candidate_ids": list(self._candidate_ids),
                "environment_candidate_ids": list(self._environment_candidate_ids),
                "command_candidate_ids": list(self._command_candidate_ids),
            },
            "exhausted_limits": list(self._exhausted_limits()),
            "termination": self._termination,
            "finalized_at": self._finalized_at,
            "created_at": self._created_at,
            "updated_at": self._now(),
        }

    def _resume_locked(self) -> None:
        persisted = json.loads(self.path.read_text(encoding="utf-8"))
        if persisted.get("limits") != self._limits_dict() or persisted.get("pricing") != asdict(
            self.pricing
        ):
            raise ValueError("Existing budget ledger uses different limits or pricing")
        usage = persisted.get("usage") or {}
        self._requests_started = int(usage.get("requests_started", 0))
        self._responses_completed = int(usage.get("responses_completed", 0))
        self._request_errors = int(usage.get("request_errors", 0))
        self._input_tokens = int(usage.get("input_tokens", 0))
        self._output_tokens = int(usage.get("output_tokens", 0))
        self._cache_read_tokens = int(usage.get("cache_read_tokens", 0))
        self._candidates = int(usage.get("candidates", 0))
        self._environments = int(usage.get("environments", 0))
        self._commands = int(usage.get("commands", 0))
        trace = persisted.get("execution_trace") or {}
        self._candidate_ids = [str(item) for item in trace.get("candidate_ids", [])]
        self._environment_candidate_ids = [
            str(item) for item in trace.get("environment_candidate_ids", [])
        ]
        self._command_candidate_ids = [
            str(item) for item in trace.get("command_candidate_ids", [])
        ]
        self._created_at = str(persisted.get("created_at") or self._created_at)
        self._termination = persisted.get("termination")
        self._finalized_at = persisted.get("finalized_at")

    def _require_open_locked(self) -> None:
        if self._finalized_at is not None:
            raise RuntimeError("Online budget ledger is finalized")

    def _write_locked(self) -> dict[str, Any]:
        snapshot = self._snapshot_locked()
        write_json(self.path, snapshot)
        return snapshot

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            if self.path.is_file():
                self._resume_locked()
            return self._snapshot_locked()

    def preflight(self) -> None:
        with self._lock:
            if self.path.is_file():
                self._resume_locked()
            self._require_open_locked()
            exhausted = self._exhausted_limits()
            if exhausted:
                scope = exhausted[0]
                self._termination = {
                    "kind": "budget_exhausted",
                    "scope": scope,
                    "observed_before_request": self._snapshot_locked()["usage"],
                    "timestamp": self._now(),
                }
                snapshot = self._write_locked()
                raise BudgetExceeded(scope, snapshot)
            self._requests_started += 1
            self._write_locked()

    def record_response(self, usage: UsageDelta) -> dict[str, Any]:
        with self._lock:
            if self.path.is_file():
                self._resume_locked()
            self._require_open_locked()
            self._responses_completed += 1
            self._input_tokens += usage.input_tokens
            self._output_tokens += usage.output_tokens
            self._cache_read_tokens += usage.cache_read_tokens
            return self._write_locked()

    def record_error(self) -> dict[str, Any]:
        with self._lock:
            if self.path.is_file():
                self._resume_locked()
            self._require_open_locked()
            self._request_errors += 1
            return self._write_locked()

    def _reserve_execution(self, scope: str, candidate_id: str) -> None:
        with self._lock:
            if self.path.is_file():
                self._resume_locked()
            self._require_open_locked()
            exhausted = self._exhausted_limits()
            if scope in exhausted or "wall_clock_seconds" in exhausted:
                exhausted_scope = "wall_clock_seconds" if "wall_clock_seconds" in exhausted else scope
                self._termination = {
                    "kind": "budget_exhausted",
                    "scope": exhausted_scope,
                    "timestamp": self._now(),
                }
                snapshot = self._write_locked()
                raise BudgetExceeded(exhausted_scope, snapshot)
            if scope == "candidates":
                self._candidates += 1
                self._candidate_ids.append(candidate_id)
            elif scope == "environments":
                self._environments += 1
                self._environment_candidate_ids.append(candidate_id)
            elif scope == "commands":
                self._commands += 1
                self._command_candidate_ids.append(candidate_id)
            else:
                raise ValueError(f"Unknown execution budget scope: {scope}")
            self._write_locked()

    def reserve_candidate(self, candidate_id: str) -> None:
        self._reserve_execution("candidates", candidate_id)

    def reserve_environment(self, candidate_id: str) -> None:
        self._reserve_execution("environments", candidate_id)

    def reserve_command(self, candidate_id: str) -> None:
        self._reserve_execution("commands", candidate_id)

    def finalize(self) -> dict[str, Any]:
        with self._lock:
            if self.path.is_file():
                self._resume_locked()
            if self._finalized_at is None:
                self._finalized_at = self._now()
            return self._write_locked()
