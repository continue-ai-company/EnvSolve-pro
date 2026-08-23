#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.verifier_handoff_screen import (
    adjudicate_screen,
    build_paired_schedule,
)


def _retry_mapping(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        source, separator, retry = value.partition("=")
        if not separator or not source or not retry:
            raise ValueError("Official retry must have SOURCE_RUN_ID=RETRY_RUN_ID form")
        if source in result:
            raise ValueError(f"Duplicate Official retry source: {source}")
        result[source] = retry
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Adjudicate a verifier-handoff control screen and derive its pair schedule."
    )
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paired-schedule-output", type=Path)
    parser.add_argument(
        "--official-retry",
        action="append",
        default=[],
        metavar="SOURCE=RETRY",
    )
    args = parser.parse_args()

    result = adjudicate_screen(
        args.schedule,
        args.runs_root,
        official_retries=_retry_mapping(args.official_retry),
    )
    write_json(args.output, result)
    if args.paired_schedule_output is not None:
        paired = build_paired_schedule(result, read_json(args.schedule))
        write_json(args.paired_schedule_output, paired)
    print(
        f"scheduled={result['counts']['scheduled']} "
        f"eligible={result['counts']['scientifically_eligible']} "
        f"pass={result['counts']['official_pass']} "
        f"fail={result['counts']['official_fail']} "
        f"censored={result['counts']['censored']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
