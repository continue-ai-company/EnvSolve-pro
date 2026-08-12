#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

# ruff: noqa: E402 - install the repository root before experiment imports.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.runners.certification_repair_boundary_v4 import (
    BoundaryV4QualifiedCodexCliRunner,
    BoundaryV4QualifiedMinimalBRunner,
    BoundaryV4QualifiedOneShotRunner,
)
from experiments import run_schedule
from experiments.extensible_schedule import install_runner_entrypoints


def main() -> int:
    entrypoint = "experiments/run_replay_ablation_boundary_v4_case.py"
    install_runner_entrypoints(
        {
            BoundaryV4QualifiedCodexCliRunner.runner_name: entrypoint,
            BoundaryV4QualifiedOneShotRunner.runner_name: entrypoint,
            BoundaryV4QualifiedMinimalBRunner.runner_name: entrypoint,
        }
    )
    return run_schedule.main()


if __name__ == "__main__":
    raise SystemExit(main())
