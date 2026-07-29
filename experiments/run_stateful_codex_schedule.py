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
from experiments.run_stateful_codex_case import RUNNER_METHODS


def main() -> int:
    install_runner_entrypoints({
        runner_id: "experiments/run_stateful_codex_case.py"
        for runner_id in RUNNER_METHODS
    })
    return run_schedule.main()


if __name__ == "__main__":
    raise SystemExit(main())
