#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.runners.envsolve_pro_v2_registry import (
    register_envsolve_pro_v2_runners,
)

register_envsolve_pro_v2_runners()

from experiments.run_case import main


if __name__ == "__main__":
    raise SystemExit(main())
