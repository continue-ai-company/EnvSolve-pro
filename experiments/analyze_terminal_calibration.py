#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.calibration_analysis import analyze_terminal_calibration
from envsolve_harness.core.io import write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit and summarize a frozen terminal calibration batch."
    )
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, default=ROOT / "runs")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    analysis = analyze_terminal_calibration(
        args.bindings,
        args.preregistration,
        args.runs_root,
        ROOT,
    )
    write_json(args.output, analysis)
    aggregate = analysis["aggregate"]
    print(f"analysis={args.output.resolve()}")
    print(
        f"runs={aggregate['runs']} valid={aggregate['audit_valid']} "
        f"completed={aggregate['evaluation_completed']} "
        f"passes={aggregate['official_pass']} unknown={aggregate['official_unknown']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
