#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from envsolve.runtime.policy import StructuredModelDeploymentPolicy
from envsolve.state import EnvironmentState
from envsolve_harness.budget.langchain import create_budgeted_chat_model
from envsolve_harness.core.config import load_harness_config
from envsolve_harness.core.io import read_json, write_json


class SafeResponseDiagnostics(BaseCallbackHandler):
    def __init__(self) -> None:
        self.responses: list[dict[str, Any]] = []

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        for group in response.generations:
            for generation in group:
                message = getattr(generation, "message", None)
                metadata = getattr(message, "response_metadata", None)
                metadata = metadata if isinstance(metadata, dict) else {}
                usage = getattr(message, "usage_metadata", None)
                usage = usage if isinstance(usage, dict) else {}
                output_details = usage.get("output_token_details")
                output_details = (
                    output_details if isinstance(output_details, dict) else {}
                )
                additional = getattr(message, "additional_kwargs", None)
                additional = additional if isinstance(additional, dict) else {}
                self.responses.append(
                    {
                        "status": "completed",
                        "finish_reason": metadata.get("finish_reason"),
                        "input_tokens": usage.get("input_tokens"),
                        "output_tokens": usage.get("output_tokens"),
                        "reasoning_tokens": output_details.get("reasoning"),
                        "reasoning_content_present": bool(
                            additional.get("reasoning")
                            or additional.get("reasoning_content")
                        ),
                    }
                )

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        completion = getattr(error, "completion", None)
        usage = getattr(completion, "usage", None)
        choices = getattr(completion, "choices", None) or ()
        choice = choices[0] if choices else None
        self.responses.append(
            {
                "status": "error",
                "error_type": type(error).__name__,
                "finish_reason": getattr(choice, "finish_reason", None),
                "input_tokens": getattr(usage, "prompt_tokens", None),
                "output_tokens": getattr(usage, "completion_tokens", None),
                "reasoning_tokens": getattr(
                    getattr(usage, "completion_tokens_details", None),
                    "reasoning_tokens",
                    None,
                ),
                "reasoning_content_present": bool(
                    getattr(getattr(choice, "message", None), "reasoning", None)
                    or getattr(
                        getattr(choice, "message", None),
                        "reasoning_content",
                        None,
                    )
                ),
            }
        )


def _synthetic_state() -> EnvironmentState:
    state = EnvironmentState(
        "synthetic-output-contract",
        case={
            "case_id": "synthetic-output-contract",
            "repository": "synthetic/repository-free",
            "revision": "0" * 40,
        },
    )
    generic_log = "\n".join(
        f"dependency-group-{index}: generic package constraint remains unresolved"
        for index in range(80)
    )
    state.actions["candidate-synthetic"] = {
        "action_id": "candidate-synthetic",
        "command": "python -m pip install -e .",
        "status": "failed",
        "exit_code": 1,
        "observation": {
            "duration_seconds": 12.0,
            "stdout": "",
            "stderr": generic_log,
        },
        "state_metadata": {"event_sequence": 1},
    }
    state.verifications.append(
        {
            "verification_id": "verification-synthetic",
            "verifier": "synthetic-fixed-check",
            "passed": False,
            "details": {
                "candidate_id": "candidate-synthetic",
                "feedback_channel": "internal-execution-only",
                "check_profile": "two-layer",
                "summary": "Generic dependency constraints remain unresolved",
                "counterexample_count": 80,
                "verifier_details": {"diagnostic": generic_log},
            },
        }
    )
    return state


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run_probe(config_path: Path, requests: int) -> dict[str, Any]:
    config = load_harness_config(config_path, ROOT)
    model_name = "deepseek/deepseek-v4-pro"
    pricing = config.model_pricing[model_name]
    diagnostics = SafeResponseDiagnostics()
    with tempfile.TemporaryDirectory() as directory:
        ledger_path = Path(directory) / "ledger.json"
        model = create_budgeted_chat_model(
            model=model_name,
            callbacks=[diagnostics],
            budget_ledger_path=str(ledger_path),
            budget_max_model_requests=requests,
            budget_max_total_tokens=config.model_max_total_tokens,
            budget_max_estimated_cost_usd=config.model_max_estimated_cost_usd,
            budget_input_cost_per_million=pricing.input_cost_per_million,
            budget_output_cost_per_million=pricing.output_cost_per_million,
            budget_cache_read_cost_per_million=pricing.cache_read_cost_per_million,
            request_timeout=config.model_request_timeout,
            max_retries=config.model_max_retries,
            max_tokens=config.model_max_output_tokens,
            reasoning_effort=config.model_reasoning_effort,
            model_kwargs={"response_format": {"type": "json_object"}},
            temperature=0,
            seed=0,
        )
        policy = StructuredModelDeploymentPolicy(
            model,
            {
                "schema": "synthetic-repository-free-profile-v1",
                "files": [
                    {
                        "path": "pyproject.toml",
                        "content": "[project]\nname='synthetic'\ndependencies=[]",
                    }
                ],
            },
        )
        state = _synthetic_state()
        candidates: list[dict[str, Any]] = []
        policy_errors: list[dict[str, str]] = []
        for _ in range(requests):
            try:
                candidate = policy.propose(state)
            except Exception as exc:
                policy_errors.append({"error_type": type(exc).__name__})
                continue
            candidates.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "script_chars": len(candidate.script),
                    "script_sha256": _sha256(candidate.script),
                    "rationale_chars": len(candidate.rationale),
                    "rationale_sha256": _sha256(candidate.rationale),
                }
            )
        ledger = read_json(ledger_path)

    usage = ledger["usage"]
    qualified = bool(
        len(candidates) == requests
        and not policy_errors
        and usage["responses_completed"] == requests
        and usage["request_errors"] == 0
        and all(item.get("finish_reason") == "stop" for item in diagnostics.responses)
    )
    return {
        "schema_version": "1.0.0",
        "probe_id": "p6-model-output-contract-stress-v2",
        "purpose": "Stress the production structured policy boundary without repository or evaluator input.",
        "claim_scope": "synthetic model-protocol compatibility only",
        "request": {
            "model": model_name,
            "repository_context": False,
            "evaluator_context": False,
            "requests": requests,
            "temperature": 0,
            "seed": 0,
            "max_output_tokens": config.model_max_output_tokens,
            "reasoning_effort": config.model_reasoning_effort,
            "response_format": "json_object",
        },
        "result": {
            "qualified": qualified,
            "parsed_candidates": len(candidates),
            "policy_errors": policy_errors,
            "responses": diagnostics.responses,
            "usage": usage,
            "candidates": candidates,
        },
        "privacy": {
            "candidate_content_persisted": False,
            "reasoning_content_persisted": False,
            "api_key_persisted": False,
        },
        "interpretation": "A pass qualifies only the provider/client output boundary under synthetic pressure; it is not repository-deployment evidence.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe the model output contract.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--requests", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.requests < 1:
        raise ValueError("requests must be positive")
    result = run_probe(args.config.resolve(), args.requests)
    write_json(args.output, result)
    print(
        f"output={args.output.resolve()} qualified={result['result']['qualified']} "
        f"parsed={result['result']['parsed_candidates']}"
    )
    return 0 if result["result"]["qualified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
