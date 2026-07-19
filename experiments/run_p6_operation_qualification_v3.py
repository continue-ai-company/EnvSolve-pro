#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the frozen P6 operation Q3 schedule.")
    parser.add_argument(
        "--schedule",
        type=Path,
        default=ROOT / "experiments/validations/p6_operation_qualification_v3_schedule.json",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "experiments/configs/local_mac_p6_operation.json",
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "experiments/protocols/envbench_python_official_v1.json",
    )
    parser.add_argument("--start-position", type=int, default=1)
    parser.add_argument("--stop-position", type=int)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.start_position < 1:
        raise ValueError("--start-position must be positive")
    if args.stop_position is not None and args.stop_position < args.start_position:
        raise ValueError("--stop-position must be at least --start-position")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")
    schedule = json.loads(args.schedule.resolve().read_text(encoding="utf-8"))
    case_file = ROOT / schedule["case_file"]
    outcomes = []
    for episode in schedule["episodes"]:
        if episode["position"] < args.start_position:
            continue
        if args.stop_position is not None and episode["position"] > args.stop_position:
            break
        command = [
            sys.executable,
            str(ROOT / "experiments/run_case.py"),
            "--case-file", str(case_file),
            "--case-id", episode["case_id"],
            "--run-id", episode["run_id"],
            "--runner", "envsolve",
            "--method", episode["method"],
            "--model", schedule["model"],
            "--seed", str(episode["seed"]),
            "--config", str(args.config.resolve()),
            "--protocol", str(args.protocol.resolve()),
        ]
        if args.overwrite:
            command.append("--overwrite")
        print(
            f"position={episode['position']} case={episode['case_id']} "
            f"method={episode['method']}",
            flush=True,
        )
        process = subprocess.run(command, cwd=ROOT, check=False)
        outcomes.append(
            {
                "position": episode["position"],
                "case_id": episode["case_id"],
                "method": episode["method"],
                "process_exit_code": process.returncode,
            }
        )
        output = ROOT / "experiments/runs/p6-operation-q3-progress.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "schedule": str(args.schedule.resolve()),
                    "start_position": args.start_position,
                    "stop_position": args.stop_position,
                    "outcomes": outcomes,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return 0 if all(item["process_exit_code"] == 0 for item in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())

