#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.integrity.freeze import (
    FREEZE_MANIFEST_PATH,
    build_harness_freeze,
    verify_harness_freeze,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify the machine-readable harness freeze."
    )
    parser.add_argument("--verify", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=WORKSPACE_ROOT / FREEZE_MANIFEST_PATH,
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if args.verify:
        report = verify_harness_freeze(WORKSPACE_ROOT, read_json(output))
        print(json.dumps({"valid": report.valid, "errors": report.errors}, indent=2))
        return 0 if report.valid else 1

    freeze = build_harness_freeze(
        WORKSPACE_ROOT,
        datetime.now(timezone.utc).isoformat(),
    )
    write_json(output, freeze)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
