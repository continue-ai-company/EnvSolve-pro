#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ruff: noqa: E402 - load the workspace package before parsing arguments.

from envsolve_harness.core.config import load_harness_config
from envsolve_harness.core.io import load_case, write_json
from envsolve_harness.core.models import RunSpec
from envsolve_harness.core.protocol import load_protocol
from envsolve_harness.runners.progress_agent import PROGRESS_METHODS
from envsolve_harness.runners.registry import RunnerOptions
from experiments.run_project_progress_case import _arm, _factory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay one fixed progress candidate without invoking a model."
    )
    parser.add_argument("--case-file", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--program", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    case = load_case(args.case_file.resolve(), args.case_id)
    config = load_harness_config(args.config.resolve(), ROOT)
    protocol = load_protocol(args.protocol.resolve())
    arm = _arm()
    run_spec = RunSpec(
        f"{args.source_run_id}-exact-qualification-replay",
        PROGRESS_METHODS[arm],
        None,
        None,
    )
    runner = _factory(config, protocol, run_spec, RunnerOptions())
    program_path = args.program.resolve()
    output_root = args.output_root.resolve()
    result = runner.replay_program(
        case,
        program=program_path.read_text(encoding="utf-8"),
        root=output_root,
    )
    result["probe"] = {
        "kind": "exact-candidate-qualification-replay",
        "source_program": str(program_path),
        "source_run_id": args.source_run_id,
        "model_invoked": False,
        "state_updated": False,
    }
    write_json(output_root / "result.json", result)
    print(f"status={result.get('status')}")
    print(f"certified={str(result.get('certified') is True).lower()}")
    print(f"artifacts={output_root}")
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
