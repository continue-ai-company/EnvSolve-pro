#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

# ruff: noqa: E402 - install the repository root before experiment imports.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.runners.certification_repair_boundary_v2 import (
    BoundaryV2QualifiedCodexCliRunner,
    BoundaryV2QualifiedMinimalBRunner,
    BoundaryV2QualifiedOneShotRunner,
)
from experiments import run_schedule
from experiments.extensible_schedule import install_runner_entrypoints


def main() -> int:
    entrypoint = "experiments/run_replay_ablation_boundary_v2_case.py"
    install_runner_entrypoints(
        {
            BoundaryV2QualifiedCodexCliRunner.runner_name: entrypoint,
            BoundaryV2QualifiedOneShotRunner.runner_name: entrypoint,
            BoundaryV2QualifiedMinimalBRunner.runner_name: entrypoint,
        }
    )
    return run_schedule.main()


if __name__ == "__main__":
    raise SystemExit(main())
