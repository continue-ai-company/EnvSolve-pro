#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor, as_completed
from pathlib import Path
import signal
import subprocess
import sys
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve_harness.core.config import load_harness_config
from envsolve_harness.core.io import read_jsonl, write_json
from envsolve_harness.core.models import Case
from envsolve_harness.execution.batch import (
    BatchProcessController,
    cleanup_case_containers,
    mark_case_interrupted,
)
from envsolve_harness.runners.registry import registered_solver_runners
from envsolve_harness.storage.artifacts import safe_name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and evaluate a batch of environment cases.")
    parser.add_argument("--case-file", type=Path, required=True)
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
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--config", type=Path, default=WORKSPACE_ROOT / "experiments/configs/local_mac.json")
    parser.add_argument(
        "--protocol",
        type=Path,
        default=WORKSPACE_ROOT / "experiments/protocols/envbench_python_official_v1.json",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def _empty_result(case: Case, state: str, error: str) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "repository": case.repository,
        "revision": case.revision,
        "state": state,
        "process_exit_code": None,
        "stdout": "",
        "stderr": error,
        "cleaned_container_ids": [],
        "artifact_interruption_recorded": False,
    }


def run_case(
    case: Case,
    args: argparse.Namespace,
    controller: BatchProcessController,
    runs_root: Path,
) -> dict[str, Any]:
    if controller.cancelled:
        return _empty_result(case, "not_started", controller.reason or "Batch cancelled")
    command = [
        sys.executable,
        str(WORKSPACE_ROOT / "experiments/run_case.py"),
        "--case-file", str(args.case_file.resolve()),
        "--case-id", case.case_id,
        "--run-id", args.run_id,
        "--runner", args.runner,
        "--config", str(args.config.resolve()),
        "--protocol", str(args.protocol.resolve()),
    ]
    if args.method:
        command.extend(["--method", args.method])
    if args.model:
        command.extend(["--model", args.model])
    if args.source_run:
        command.extend(["--source-run", str(args.source_run.resolve())])
    if args.seed is not None:
        command.extend(["--seed", str(args.seed)])
    if args.overwrite:
        command.append("--overwrite")
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except OSError as exc:
        return _empty_result(case, "process_error", f"{type(exc).__name__}: {exc}")
    controller.register(case.case_id, process)
    try:
        stdout, stderr = process.communicate()
    finally:
        controller.unregister(case.case_id)

    interrupted = controller.was_interrupted(case.case_id)
    cleaned_container_ids: tuple[str, ...] = ()
    case_root = runs_root / safe_name(args.run_id) / safe_name(case.case_id)
    if interrupted:
        cleaned_container_ids = cleanup_case_containers(case_root)
        interruption_recorded = mark_case_interrupted(
            case_root,
            controller.reason or "Batch cancelled",
            process.returncode,
            cleaned_container_ids,
        )
    else:
        interruption_recorded = False
    return {
        "case_id": case.case_id,
        "repository": case.repository,
        "revision": case.revision,
        "state": "interrupted" if interrupted else "process_finished",
        "process_exit_code": process.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "cleaned_container_ids": list(cleaned_container_ids),
        "artifact_interruption_recorded": interruption_recorded,
    }


class BatchTermination(Exception):
    def __init__(self, signal_number: int) -> None:
        super().__init__(f"Received signal {signal_number}")
        self.signal_number = signal_number


def main() -> int:
    args = parse_args()
    if args.max_workers < 1:
        raise ValueError("--max-workers must be positive")
    cases = [Case.from_dict(record) for record in read_jsonl(args.case_file.resolve())]
    config = load_harness_config(args.config.resolve(), WORKSPACE_ROOT)
    results_by_id: dict[str, dict[str, Any]] = {}
    controller = BatchProcessController()
    executor = ThreadPoolExecutor(max_workers=args.max_workers)
    futures: dict[Future[dict[str, Any]], Case] = {
        executor.submit(run_case, case, args, controller, config.runs_root): case for case in cases
    }
    interrupted = False
    termination_signal: int | None = None
    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def terminate_on_signal(signal_number: int, _frame: Any) -> None:
        raise BatchTermination(signal_number)

    signal.signal(signal.SIGTERM, terminate_on_signal)
    try:
        for future in as_completed(futures):
            result = future.result()
            results_by_id[result["case_id"]] = result
            print(
                f"case={result['case_id']} process_exit_code={result['process_exit_code']}",
                flush=True,
            )
    except (KeyboardInterrupt, BatchTermination) as exc:
        interrupted = True
        termination_signal = signal.SIGINT if isinstance(exc, KeyboardInterrupt) else exc.signal_number
        reason = f"batch interrupted by signal {termination_signal}"
        controller.cancel(reason)
        for future in futures:
            future.cancel()
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
        signal.signal(signal.SIGTERM, previous_sigterm)

    for future, case in futures.items():
        if case.case_id in results_by_id:
            continue
        if future.cancelled():
            results_by_id[case.case_id] = _empty_result(
                case, "not_started", controller.reason or "Batch cancelled before start"
            )
            continue
        try:
            result = future.result()
        except CancelledError:
            result = _empty_result(case, "not_started", "Batch cancelled before start")
        except BaseException as exc:
            result = _empty_result(case, "process_error", f"{type(exc).__name__}: {exc}")
        results_by_id[case.case_id] = result

    ordered_results = [results_by_id[case.case_id] for case in cases]
    summary_path = config.runs_root / safe_name(args.run_id) / "batch_summary.json"
    write_json(
        summary_path,
        {
            "schema_version": "1.1.0",
            "run_id": args.run_id,
            "runner": args.runner,
            "model": args.model,
            "seed": args.seed,
            "case_file": str(args.case_file.resolve()),
            "max_workers": args.max_workers,
            "interrupted": interrupted,
            "termination_signal": termination_signal,
            "results": ordered_results,
        },
    )
    failed = sum(
        result["state"] == "process_error"
        or (
            result["process_exit_code"] is not None
            and result["process_exit_code"] != 0
            and result["state"] != "interrupted"
        )
        for result in ordered_results
    )
    interrupted_cases = sum(result["state"] == "interrupted" for result in ordered_results)
    not_started = sum(result["state"] == "not_started" for result in ordered_results)
    print(f"summary={summary_path}")
    print(
        f"cases={len(cases)} failed_processes={failed} "
        f"interrupted={interrupted_cases} not_started={not_started}"
    )
    if interrupted:
        return 128 + (termination_signal or signal.SIGINT)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
