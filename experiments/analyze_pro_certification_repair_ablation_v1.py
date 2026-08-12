#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.certification_repair_analysis import (
    analyze_certification_repair_ablation,
)
from envsolve_harness.core.io import write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze the frozen EnvSolve-Pro certification-repair Dev-8."
    )
    parser.add_argument("--adjudication", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = analyze_certification_repair_ablation(
        args.adjudication,
        args.runs_root,
    )
    write_json(args.output, result)
    arms = result["primary"]["by_arm"]
    mechanism = result["mechanism"]["by_arm"]["C"]
    print(f"analysis={args.output.resolve()}")
    print(
        "official_pass_at_1="
        f"A:{arms['A']['official_pass_at_1']}/8 "
        f"B:{arms['B']['official_pass_at_1']}/8 "
        f"C:{arms['C']['official_pass_at_1']}/8"
    )
    print(
        f"C_repair_opportunities={mechanism['repair_opportunity']} "
        f"activated={mechanism['activated_repair']} "
        f"successful={mechanism['repair_success']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
