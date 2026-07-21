#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
ENVBENCH = ROOT / "EnvBench"
for path in (ROOT, ENVBENCH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from envsolve.v0.agent import VerifierGatedPythonAgent
from envsolve_harness.budget.langchain import create_budgeted_chat_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one minimal EnvSolve v0 inference case.")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--trajectory-dir", type=Path, required=True)
    parser.add_argument("--repos-dir", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--max-iterations", type=int, required=True)
    parser.add_argument("--bash-timeout", type=int, required=True)
    parser.add_argument("--request-timeout", type=int, required=True)
    parser.add_argument("--max-retries", type=int, required=True)
    parser.add_argument("--max-output-tokens", type=int, required=True)
    parser.add_argument("--max-model-requests", type=int, required=True)
    parser.add_argument("--max-total-tokens", type=int, required=True)
    parser.add_argument("--max-cost-usd", type=float, required=True)
    parser.add_argument("--input-cost", type=float, required=True)
    parser.add_argument("--output-cost", type=float, required=True)
    parser.add_argument("--cache-read-cost", type=float, required=True)
    parser.add_argument("--pricing-source-url")
    parser.add_argument("--pricing-snapshot-date")
    parser.add_argument("--seed", type=int)
    return parser.parse_args()


async def run_case(args: argparse.Namespace) -> None:
    from inference.src.async_bash_executor import AsyncBashExecutor
    from inference.src.env_setup_runner import EnvSetupRunner
    from inference.src.toolkits.bash_terminal_py import PythonBashTerminalToolkit

    args.trajectory_dir.mkdir(parents=True, exist_ok=True)
    args.repos_dir.mkdir(parents=True, exist_ok=True)
    model_kwargs = {
        "request_timeout": args.request_timeout,
        "max_retries": args.max_retries,
        "max_tokens": args.max_output_tokens,
        "temperature": 0,
    }
    if args.seed is not None:
        model_kwargs["seed"] = args.seed
    model = create_budgeted_chat_model(
        model=args.model,
        budget_ledger_path=str(args.ledger),
        budget_max_model_requests=args.max_model_requests,
        budget_max_total_tokens=args.max_total_tokens,
        budget_max_estimated_cost_usd=args.max_cost_usd,
        budget_input_cost_per_million=args.input_cost,
        budget_output_cost_per_million=args.output_cost,
        budget_cache_read_cost_per_million=args.cache_read_cost,
        budget_pricing_source_url=args.pricing_source_url,
        budget_pricing_snapshot_date=args.pricing_snapshot_date,
        **model_kwargs,
    )
    executor = await AsyncBashExecutor.create(
        repository=args.repository,
        revision=args.revision,
        image=args.image,
        hf_name="JetBrains-Research/EnvBench",
        output_dir=str(args.repos_dir),
        language="python",
        clear_repo=False,
        repository_workdir=True,
        container_start_timeout=300,
        bash_timeout=args.bash_timeout,
        max_num_chars_bash_output=16000,
    )
    toolkit = await PythonBashTerminalToolkit.create(bash_executor=executor)
    try:
        agent = VerifierGatedPythonAgent(model, toolkit, args.max_iterations)
        runner = EnvSetupRunner(
            repository=args.repository,
            revision=args.revision,
            agent=agent,
            log_trajectory=True,
            logging_dir=str(args.trajectory_dir),
        )
        await runner.arun()
    finally:
        await toolkit.clean()


def main() -> int:
    args = parse_args()
    if args.max_iterations < 1 or args.max_model_requests < 1:
        raise ValueError("iteration and model-request budgets must be positive")
    asyncio.run(run_case(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
