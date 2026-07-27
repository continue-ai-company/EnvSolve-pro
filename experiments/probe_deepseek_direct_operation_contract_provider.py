#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import write_json
from experiments import probe_operation_contract_provider as shared_probe


MODEL = "deepseek-v4-pro"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe the operation contract through DeepSeek's direct API."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--requests", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.requests < 1:
        raise ValueError("requests must be positive")
    original_model = shared_probe.MODEL
    shared_probe.MODEL = MODEL
    try:
        result = shared_probe.run_probe(
            args.config.resolve(),
            args.requests,
        )
    finally:
        shared_probe.MODEL = original_model
    result["probe_id"] = (
        "envsolve-pro-operation-contract-deepseek-direct-provider-v1"
    )
    result["request"]["provider"] = "deepseek-direct"
    result["request"]["base_url"] = "https://api.deepseek.com"
    write_json(args.output, result)
    print(
        f"output={args.output.resolve()} "
        f"qualified={result['result']['qualified']} "
        f"parsed={result['result']['parsed_candidates']}"
    )
    return 0 if result["result"]["qualified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
