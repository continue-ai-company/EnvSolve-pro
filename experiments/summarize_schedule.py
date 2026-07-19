#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import write_json
from envsolve_harness.results import summarize_schedule


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit and summarize a frozen schedule.")
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, default=ROOT / "runs")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--treatment-method")
    parser.add_argument("--control-method")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = summarize_schedule(
        args.schedule,
        args.runs_root,
        treatment_method=args.treatment_method,
        control_method=args.control_method,
    )
    write_json(args.output, summary)
    print(f"summary={args.output.resolve()}")
    print(
        f"runs={summary['descriptive']['runs']} "
        f"artifact_valid={summary['descriptive']['artifact_integrity_valid']} "
        f"scientifically_eligible={summary['scientific']['eligible_runs']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
