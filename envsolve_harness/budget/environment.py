from __future__ import annotations

import os
from pathlib import Path

from envsolve_harness.budget.ledger import BudgetLedger, BudgetLimits, TokenPricing


def budget_ledger_from_environment(prefix: str = "ENVSOLVE_BUDGET_") -> BudgetLedger | None:
    ledger_path = os.environ.get(f"{prefix}LEDGER_PATH")
    if not ledger_path:
        return None

    def required(name: str) -> str:
        value = os.environ.get(f"{prefix}{name}")
        if value is None or value == "":
            raise ValueError(f"Missing required budget environment variable: {prefix}{name}")
        return value

    cache_rate = os.environ.get(f"{prefix}CACHE_READ_COST_PER_MILLION")
    return BudgetLedger(
        Path(ledger_path),
        BudgetLimits(
            max_model_requests=int(required("MAX_MODEL_REQUESTS")),
            max_total_tokens=int(required("MAX_TOTAL_TOKENS")),
            max_estimated_cost_usd=float(required("MAX_ESTIMATED_COST_USD")),
        ),
        TokenPricing(
            model=required("MODEL"),
            input_cost_per_million=float(required("INPUT_COST_PER_MILLION")),
            output_cost_per_million=float(required("OUTPUT_COST_PER_MILLION")),
            cache_read_cost_per_million=float(cache_rate) if cache_rate else None,
            source_url=os.environ.get(f"{prefix}PRICING_SOURCE_URL"),
            snapshot_date=os.environ.get(f"{prefix}PRICING_SNAPSHOT_DATE"),
        ),
    )
