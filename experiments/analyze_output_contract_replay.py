#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import write_json
from envsolve_harness.output_contract_analysis import analyze_output_contract_replay


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit and summarize a preregistered output-contract replay."
    )
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, default=ROOT / "runs")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    analysis = analyze_output_contract_replay(
        args.schedule,
        args.preregistration,
        args.runs_root,
    )
    write_json(args.output, analysis)
    run = analysis["run"]
    print(f"analysis={args.output.resolve()}")
    print(
        f"valid={run['audit_valid']} responses={run['usage']['responses_completed']} "
        f"proposals={run['counts']['proposals']} decision={analysis['decision']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
