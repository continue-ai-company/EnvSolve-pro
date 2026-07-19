#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve.state import EventStore, EventType
from envsolve_harness.core.io import load_case, write_json


def _payload(value: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("--payload must be a JSON object")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create and inspect an EnvSolve state event log.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Initialize a state log from a frozen case.")
    init.add_argument("--log", type=Path, required=True)
    init.add_argument("--case-file", type=Path, required=True)
    init.add_argument("--case-id")

    append = subparsers.add_parser("append", help="Append one validated state event.")
    append.add_argument("--log", type=Path, required=True)
    append.add_argument("--case-id", required=True)
    append.add_argument("--event-type", choices=[event.value for event in EventType], required=True)
    append.add_argument("--payload", type=_payload, required=True)

    inspect = subparsers.add_parser("inspect", help="Verify and reconstruct a state log.")
    inspect.add_argument("--log", type=Path, required=True)
    inspect.add_argument("--case-id", required=True)
    inspect.add_argument("--snapshot-out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "init":
        case = load_case(args.case_file.resolve(), args.case_id)
        store = EventStore(args.log.resolve(), case.case_id)
        if store.read():
            raise ValueError(f"State log already contains events: {store.path}")
        event = store.append(EventType.RUN_STARTED, {"case": case.to_dict()})
        print(json.dumps(event.to_dict(), indent=2, sort_keys=True))
        return 0

    store = EventStore(args.log.resolve(), args.case_id)
    if args.command == "append":
        event = store.append(args.event_type, args.payload)
        print(json.dumps(event.to_dict(), indent=2, sort_keys=True))
        return 0

    state = store.reconstruct()
    snapshot = state.to_dict()
    if args.snapshot_out:
        write_json(args.snapshot_out.resolve(), snapshot)
    print(json.dumps(snapshot, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
