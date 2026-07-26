#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

# ruff: noqa: E402 - workspace path bootstrapping must precede local imports.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.runtime.policy import StructuredModelDeploymentPolicy
from envsolve.solver import EpisodeProviderAcquisitionFailed
from envsolve.state import EnvironmentState
from envsolve_harness.budget import BudgetLedger, BudgetLimits, TokenPricing, UsageDelta
from envsolve_harness.budget.langchain import JSONResponseRetryModel
from envsolve_harness.core.io import write_json


class Response:
    def __init__(self, content: str) -> None:
        self.content = content


class ScriptedBudgetedModel:
    def __init__(self, ledger: BudgetLedger, failures: int) -> None:
        self.ledger = ledger
        self.failures = failures
        self.calls = 0

    def invoke(self, input, **kwargs):
        self.calls += 1
        attempt_id = f"synthetic-attempt-{self.calls:02d}"
        self.ledger.record_provider_attempt_start(attempt_id)
        if self.calls <= self.failures:
            self.ledger.record_error(
                provider_attempt_id=attempt_id,
                provider_metadata={
                    "error_type": "JSONDecodeError",
                    "error_message": "synthetic provider response",
                },
            )
            raise json.JSONDecodeError("synthetic provider response", "x", 0)
        self.ledger.record_response(
            UsageDelta(100, 50),
            provider_attempt_id=attempt_id,
        )
        return Response(
            json.dumps(
                {
                    "script": "python -m pip install -e .",
                    "rationale": "synthetic recovery qualification",
                }
            )
        )


def _ledger(path: Path) -> BudgetLedger:
    return BudgetLedger(
        path,
        BudgetLimits(10, 100_000, 10.0),
        TokenPricing("synthetic/provider", 1.0, 2.0),
    )


def _policy(model) -> StructuredModelDeploymentPolicy:
    return StructuredModelDeploymentPolicy(model, {"files": []})


def _state() -> EnvironmentState:
    return EnvironmentState(
        "synthetic-provider-recovery",
        case={
            "case_id": "synthetic-provider-recovery",
            "repository": "synthetic/repository-free",
            "revision": "0" * 40,
        },
    )


def _attempt_trace(snapshot: dict[str, Any]) -> list[dict[str, object]]:
    return [
        {
            key: attempt[key]
            for key in ("attempt_id", "outcome", "error_type")
            if key in attempt
        }
        for attempt in snapshot["provider_attempts"]
    ]


def run_probe() -> dict[str, object]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        recovered_ledger = _ledger(root / "recovered.json")
        recovered_model = ScriptedBudgetedModel(recovered_ledger, failures=1)
        recovered_policy = _policy(
            JSONResponseRetryModel(
                recovered_model,
                recovered_ledger,
                max_retries=2,
            )
        )
        candidate = recovered_policy.propose(_state())
        recovered_snapshot = recovered_ledger.snapshot()
        recovered_usage = recovered_snapshot["usage"]
        recovered_attempts = _attempt_trace(recovered_snapshot)

        exhausted_ledger = _ledger(root / "exhausted.json")
        exhausted_model = ScriptedBudgetedModel(exhausted_ledger, failures=3)
        exhausted_policy = _policy(
            JSONResponseRetryModel(
                exhausted_model,
                exhausted_ledger,
                max_retries=2,
            )
        )
        terminal: dict[str, object]
        try:
            exhausted_policy.propose(_state())
        except EpisodeProviderAcquisitionFailed as exc:
            terminal = {
                "exception_type": type(exc).__name__,
                "attempts": exc.attempts,
            }
        else:
            terminal = {"exception_type": None, "attempts": None}
        exhausted_snapshot = exhausted_ledger.snapshot()
        exhausted_usage = exhausted_snapshot["usage"]
        exhausted_attempts = _attempt_trace(exhausted_snapshot)

    qualified = bool(
        recovered_usage["requests_started"] == 1
        and recovered_usage["responses_completed"] == 1
        and recovered_usage["request_errors"] == 1
        and recovered_usage["provider_retries"] == 1
        and recovered_usage["provider_retry_recoveries"] == 1
        and recovered_usage["response_parse_retries"] == 1
        and recovered_usage["response_parse_recoveries"] == 1
        and exhausted_usage["requests_started"] == 1
        and exhausted_usage["request_errors"] == 3
        and exhausted_usage["provider_retries"] == 2
        and exhausted_usage["provider_retry_recoveries"] == 0
        and exhausted_usage["response_parse_retries"] == 2
        and exhausted_usage["response_parse_recoveries"] == 0
        and [item["outcome"] for item in recovered_attempts]
        == ["error", "response"]
        and [item["outcome"] for item in exhausted_attempts]
        == ["error", "error", "error"]
        and terminal["exception_type"] == "EpisodeProviderAcquisitionFailed"
        and terminal["attempts"] == 3
    )
    return {
        "schema_version": "2.0.0",
        "probe_id": "pro-provider-attempt-recovery-v2",
        "purpose": "Qualify observable bounded provider attempts under one logical model request.",
        "claim_scope": "synthetic acquisition-boundary compatibility only",
        "configuration": {
            "max_retries": 2,
            "maximum_attempts": 3,
            "retry_exception": "JSONDecodeError",
            "logical_request_count_per_branch": 1,
        },
        "result": {
            "qualified": qualified,
            "recovered": {
                "usage": recovered_usage,
                "provider_attempts": recovered_attempts,
                "candidate_id": candidate.candidate_id,
                "candidate_script_sha256": hashlib.sha256(
                    candidate.script.encode("utf-8")
                ).hexdigest(),
            },
            "exhausted": {
                "usage": exhausted_usage,
                "provider_attempts": exhausted_attempts,
                "terminal": terminal,
            },
        },
        "privacy": {
            "candidate_content_persisted": False,
            "reasoning_content_persisted": False,
            "api_key_used": False,
        },
        "interpretation": "A pass qualifies only retry accounting and terminal classification; it is not deployment evidence.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe bounded provider-response recovery."
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_probe()
    write_json(args.output, result)
    print(f"output={args.output.resolve()} qualified={result['result']['qualified']}")
    return 0 if result["result"]["qualified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
