#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
import tempfile
from typing import Any

# ruff: noqa: E402 - workspace path bootstrapping must precede local imports.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.runtime.operation_policy import (
    EvidenceDirectedDeploymentPolicy,
)
from envsolve.state import EnvironmentState
from envsolve_harness.budget.langchain import create_budgeted_chat_model
from envsolve_harness.core.config import load_harness_config
from envsolve_harness.core.io import read_json, write_json
from experiments.probe_model_output_contract import SafeResponseDiagnostics


MODEL = "deepseek/deepseek-v4-pro"


def _state() -> EnvironmentState:
    state = EnvironmentState(
        "synthetic-operation-contract",
        case={
            "case_id": "synthetic-operation-contract",
            "repository": "synthetic/repository-free",
            "revision": "0" * 40,
        },
    )
    finding = {
        "finding_id": "synthetic-missing-runtime",
        "domain": "module",
        "subject": "synthetic_runtime",
        "predicate": "present",
        "required": True,
        "observed": False,
        "provenance": {"file": "src/example.py"},
    }
    state.actions["candidate-synthetic"] = {
        "action_id": "candidate-synthetic",
        "action_type": "deployment-candidate",
        "command": "python -m pip install -e .",
        "status": "succeeded",
        "exit_code": 0,
        "observation": {},
    }
    state.verifications.append(
        {
            "verification_id": "verification-synthetic",
            "verifier": "synthetic-executable-goal",
            "passed": False,
            "details": {
                "candidate_id": "candidate-synthetic",
                "reported_passed": False,
                "summary": "one synthetic runtime finding remains active",
                "verifier_details": {
                    "completed": True,
                    "goal_passed": False,
                    "infrastructure_error": None,
                    "report_details": {
                        "goal_report": {
                            "status": "fail",
                            "finding_set_complete": True,
                            "findings": [finding],
                        }
                    },
                },
            },
        }
    )
    return state


def run_probe(config_path: Path, requests: int) -> dict[str, Any]:
    config = load_harness_config(config_path, ROOT)
    pricing = config.model_pricing[MODEL]
    diagnostics = SafeResponseDiagnostics()
    with tempfile.TemporaryDirectory() as directory:
        ledger_path = Path(directory) / "ledger.json"
        model = create_budgeted_chat_model(
            model=MODEL,
            callbacks=[diagnostics],
            budget_ledger_path=str(ledger_path),
            budget_max_model_requests=requests,
            budget_max_total_tokens=config.model_max_total_tokens,
            budget_max_estimated_cost_usd=(
                config.model_max_estimated_cost_usd
            ),
            budget_input_cost_per_million=pricing.input_cost_per_million,
            budget_output_cost_per_million=pricing.output_cost_per_million,
            budget_cache_read_cost_per_million=(
                pricing.cache_read_cost_per_million
            ),
            request_timeout=config.model_request_timeout,
            max_retries=config.model_max_retries,
            max_tokens=config.model_max_output_tokens,
            reasoning_effort=config.model_reasoning_effort,
            model_kwargs={"response_format": {"type": "json_object"}},
            temperature=0,
            seed=0,
        )
        policy = EvidenceDirectedDeploymentPolicy(
            model,
            {
                "schema": "synthetic-repository-free-profile-v1",
                "files": [
                    {
                        "path": "pyproject.toml",
                        "content": (
                            "[project]\nname='synthetic'\ndependencies=[]"
                        ),
                    }
                ],
            },
            goal_contract={
                "contract_id": "synthetic-goal",
                "description": "Resolve the synthetic runtime finding",
                "program": "synthetic verifier",
                "report_schema": "envsolve-goal-report-v1",
                "sha256": "synthetic-goal-sha",
            },
        )
        state = _state()
        candidates = []
        errors = []
        for _ in range(requests):
            try:
                candidate = policy.propose(state)
            except Exception as exc:
                errors.append(
                    {
                        "error_type": type(exc).__name__,
                        "error_message_sha256": hashlib.sha256(
                            str(exc).encode("utf-8")
                        ).hexdigest(),
                    }
                )
                continue
            contract = candidate.metadata["operation_contract"]
            candidates.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "script_sha256": candidate.script_sha256,
                    "operation_contract_id": candidate.metadata[
                        "operation_contract_id"
                    ],
                    "operation_family_id": candidate.metadata[
                        "operation_family_id"
                    ],
                    "target_count": len(contract["target_finding_ids"]),
                    "precondition_evidence_count": len(
                        contract["precondition_evidence_ids"]
                    ),
                    "expected_resolution_count": len(
                        contract["expected_resolved_finding_ids"]
                    ),
                }
            )
        ledger = read_json(ledger_path)
    usage = ledger["usage"]
    qualified = bool(
        len(candidates) == requests
        and not errors
        and usage["responses_completed"] == requests
        and usage["request_errors"] == 0
        and all(
            item.get("finish_reason") == "stop"
            for item in diagnostics.responses
        )
    )
    return {
        "schema_version": "1.0.0",
        "probe_id": "envsolve-pro-operation-contract-provider-v1",
        "claim_scope": "Synthetic provider/output compatibility only.",
        "request": {
            "model": MODEL,
            "requests": requests,
            "temperature": 0,
            "seed": 0,
            "repository_context": False,
            "official_evaluator_context": False,
            "response_format": "json_object",
        },
        "result": {
            "qualified": qualified,
            "parsed_candidates": len(candidates),
            "errors": errors,
            "responses": diagnostics.responses,
            "usage": usage,
            "candidates": candidates,
        },
        "privacy": {
            "candidate_content_persisted": False,
            "reasoning_content_persisted": False,
            "api_key_persisted": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe the evidence-directed model output contract."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--requests", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.requests < 1:
        raise ValueError("requests must be positive")
    result = run_probe(args.config.resolve(), args.requests)
    write_json(args.output, result)
    print(
        f"output={args.output.resolve()} "
        f"qualified={result['result']['qualified']} "
        f"parsed={result['result']['parsed_candidates']}"
    )
    return 0 if result["result"]["qualified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
