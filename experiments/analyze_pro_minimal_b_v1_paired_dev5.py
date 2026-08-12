#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import write_json
from envsolve_harness.minimal_b_analysis import analyze_minimal_b_paired_dev5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute the frozen EnvSolve-Pro Minimal B paired Dev-5 analysis."
    )
    parser.add_argument("--adjudication", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = analyze_minimal_b_paired_dev5(args.adjudication, args.runs_root)
    write_json(args.output, result)
    primary = result["primary"]
    treatment = result["conditions"]["treatment"]
    control = result["conditions"]["control"]
    print(f"analysis={args.output.resolve()}")
    print(
        f"pass_at_1={primary['by_condition'][treatment]['official_pass_at_1']}/5 "
        f"vs {primary['by_condition'][control]['official_pass_at_1']}/5 "
        f"mcnemar_p={primary['exact_two_sided_mcnemar_p']:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
