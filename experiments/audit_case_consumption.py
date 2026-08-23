#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.case_consumption import audit_case_consumption, read_case_ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report model-observed case identities before experiment selection."
    )
    parser.add_argument("--case-file", type=Path, required=True)
    parser.add_argument("--registry", action="append", default=[], type=Path)
    parser.add_argument("--runs-root", action="append", default=[], type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit_case_consumption(
        read_case_ids(args.case_file),
        registry_paths=args.registry,
        runs_roots=args.runs_root,
    )
    report["recorded_at"] = datetime.now(timezone.utc).isoformat()
    rendered = json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
