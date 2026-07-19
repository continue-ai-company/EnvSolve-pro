#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import write_json
from envsolve_harness.trajectory_binding import freeze_last_verified_candidates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the last verified candidate from every scheduled trajectory."
    )
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, default=ROOT / "runs")
    parser.add_argument("--scripts-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-prefix", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = freeze_last_verified_candidates(
        args.schedule,
        args.runs_root,
        args.scripts_dir,
        ROOT,
        calibration_run_prefix=args.run_prefix,
    )
    write_json(args.output, manifest)
    print(f"manifest={args.output.resolve()}")
    print(f"bindings={manifest['count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
