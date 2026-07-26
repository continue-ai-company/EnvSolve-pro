#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

# ruff: noqa: E402 - workspace path bootstrapping must precede local imports.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import write_json
from envsolve_harness.persistent_state_analysis import (
    analyze_postcondition_persistent_schedule,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit and summarize postcondition-persistent qualification."
    )
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = analyze_postcondition_persistent_schedule(
        args.schedule,
        args.runs_root,
    )
    write_json(args.output, result)
    gate = result["gate"]
    print(f"output={args.output.resolve()}")
    print(
        f"complete={gate['schedule_complete']} "
        f"integrity={gate['mechanism_integrity_valid']} "
        f"decision={gate['decision']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
