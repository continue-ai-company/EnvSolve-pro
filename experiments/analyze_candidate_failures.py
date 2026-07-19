#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import write_json
from envsolve_harness.failure_analysis import analyze_candidate_failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify candidate transition outcomes in a completed schedule."
    )
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, default=ROOT / "runs")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    analysis = analyze_candidate_failures(args.schedule, args.runs_root)
    write_json(args.output, analysis)
    aggregate = analysis["aggregate"]
    print(f"analysis={args.output.resolve()}")
    print(
        f"runs={aggregate['runs']} candidates={aggregate['candidates']} "
        f"executed={aggregate['executed_candidates']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
