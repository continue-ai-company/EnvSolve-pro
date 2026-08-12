#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments import run_schedule
from experiments.extensible_schedule import install_runner_entrypoints


def main() -> int:
    install_runner_entrypoints(
        {
            "codex-cli-qualified": "experiments/run_qualified_codex_case.py",
            "envsolve-pro-minimal-b-qualified": (
                "experiments/run_qualified_codex_case.py"
            ),
        }
    )
    return run_schedule.main()


if __name__ == "__main__":
    raise SystemExit(main())
