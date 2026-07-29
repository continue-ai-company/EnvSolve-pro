#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


# ruff: noqa: E402 - workspace path bootstrapping must precede local imports.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments import run_schedule
from experiments.extensible_schedule import install_runner_entrypoints


def main() -> int:
    run_schedule.OPENAI_API_RUNNERS = (
        run_schedule.OPENAI_API_RUNNERS
        | {
            "envsolve-pro-execution-feedback",
            "envsolve-pro-goal-frontier",
        }
    )
    install_runner_entrypoints({
        "envsolve-pro-execution-feedback": (
            "experiments/run_execution_feedback_case.py"
        ),
        "envsolve-pro-goal-frontier": "experiments/run_goal_frontier_case.py",
    })
    return run_schedule.main()


if __name__ == "__main__":
    raise SystemExit(main())
