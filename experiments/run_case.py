#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve_harness.adapters.registry import create_benchmark_adapter
from envsolve_harness.core.config import load_harness_config
from envsolve_harness.core.io import load_case
from envsolve_harness.core.models import RunSpec
from envsolve_harness.core.protocol import load_protocol
from envsolve_harness.execution.heartbeat import RunHeartbeat
from envsolve_harness.runners.registry import (
    RunnerOptions,
    create_solver_runner,
    default_method_for,
    registered_solver_runners,
)
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import initialize_manifest, update_manifest
from envsolve_harness.utils.provenance import sha256_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and evaluate an environment script for one case.")
    parser.add_argument("--case-file", type=Path, required=True)
    parser.add_argument("--case-id")
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--runner",
        choices=registered_solver_runners(),
        default="deterministic",
    )
    parser.add_argument("--method")
    parser.add_argument("--model")
    parser.add_argument("--source-run", type=Path)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--config", type=Path, default=WORKSPACE_ROOT / "experiments/configs/local_mac.json")
    parser.add_argument(
        "--protocol",
        type=Path,
        default=WORKSPACE_ROOT / "experiments/protocols/envbench_python_official_v1.json",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    case = load_case(args.case_file.resolve(), args.case_id)
    config = load_harness_config(args.config.resolve(), WORKSPACE_ROOT)
    protocol = load_protocol(args.protocol.resolve())
    method = args.method or default_method_for(args.runner)
    run_spec = RunSpec(args.run_id, method, args.model, args.seed)
    try:
        artifacts = RunArtifacts.create(
            config.runs_root,
            args.run_id,
            case.case_id,
            overwrite=args.overwrite,
        )
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    manifest = initialize_manifest(artifacts, config, case, run_spec, protocol)
    monitor = manifest["runtime_monitor"]
    monitor["state"] = "running"
    update_manifest(artifacts, runtime_monitor=monitor)
    heartbeat = RunHeartbeat(
        artifacts.runtime_heartbeat,
        interval_seconds=float(monitor["interval_seconds"]),
        suspend_gap_seconds=float(monitor["suspend_gap_seconds"]),
    )
    try:
        with heartbeat:
            runner = create_solver_runner(
                args.runner,
                config,
                protocol,
                run_spec,
                RunnerOptions(args.source_run.resolve() if args.source_run else None),
            )
            solver_result = runner.run(case, artifacts, run_spec)
            if not solver_result.generation_completed or solver_result.script_path is None:
                print(f"generation_completed=false\nerror={solver_result.error}")
                print(f"artifacts={artifacts.root}")
                exit_code = 1
            else:
                generated_script = artifacts.root / solver_result.script_path
                result = create_benchmark_adapter(config, protocol).evaluate(
                    case, generated_script, artifacts, run_spec
                )
                print(f"artifacts={artifacts.root}")
                print("generation_completed=true")
                print(f"evaluation_completed={str(result.evaluation_completed).lower()}")
                print(f"official_pass={str(result.official_pass).lower()}")
                print(f"benchmark={result.benchmark}")
                print(f"raw_metrics={result.raw_metrics}")
                exit_code = 0 if result.evaluation_completed else 1
    finally:
        if artifacts.runtime_heartbeat.is_file():
            monitor["state"] = "completed"
            monitor["sha256"] = sha256_file(artifacts.runtime_heartbeat)
            update_manifest(artifacts, runtime_monitor=monitor)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
