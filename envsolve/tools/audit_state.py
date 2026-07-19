#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve.state import audit_state_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit an EnvSolve event log and its materialized snapshot."
    )
    parser.add_argument("--event-log", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    args = parser.parse_args()
    report = audit_state_artifacts(
        args.event_log.resolve(),
        args.snapshot.resolve(),
        args.case_id,
    )
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
