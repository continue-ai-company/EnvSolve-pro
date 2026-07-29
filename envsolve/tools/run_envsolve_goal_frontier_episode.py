#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

# ruff: noqa: E402 - workspace path bootstrapping must precede local imports.

ROOT = Path(__file__).resolve().parents[2]
ENVBENCH = ROOT / "EnvBench"
for path in (ROOT, ENVBENCH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from envsolve.runtime.goal_frontier_policy import GoalFrontierDeploymentPolicy
from envsolve.tools import run_envsolve_episode


def main() -> int:
    run_envsolve_episode.StructuredModelDeploymentPolicy = (
        GoalFrontierDeploymentPolicy
    )
    return run_envsolve_episode.main()


if __name__ == "__main__":
    raise SystemExit(main())
