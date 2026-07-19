#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve_harness.audit import audit_run


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit an EnvSolve run artifact directory.")
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    report = audit_run(args.run_dir)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

