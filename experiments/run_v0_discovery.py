#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve_harness.core.config import load_harness_config
from envsolve_harness.core.io import read_json, read_jsonl, write_json
from envsolve_harness.execution.batch import (
    BatchProcessController,
    cleanup_case_containers,
    mark_case_interrupted,
)
from envsolve_harness.storage.artifacts import safe_name


PREREGISTRATION = (
    WORKSPACE_ROOT
    / "experiments/validations/envsolve_v0_discovery5_round1_preregistration.json"
)
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
RUN_IDS = {
    "envsolve_v0": "envsolve-v0-discovery5-r1-v0",
    "freeagent": "envsolve-v0-discovery5-r1-freeagent",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_schedule(
    records: list[dict[str, Any]],
    run_ids: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    run_ids = run_ids or RUN_IDS
    schedule: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        conditions = (
            ("envsolve_v0", "freeagent")
            if index % 2
            else ("freeagent", "envsolve_v0")
        )
        for condition in conditions:
            schedule.append(
                {
                    "case_rank": index,
                    "case_id": str(record["case_id"]),
                    "repository": str(record["repository"]),
                    "revision": str(record["revision"]),
                    "condition": condition,
                    "run_id": run_ids[condition],
                }
            )
    return schedule


def _redact(value: str) -> str:
    return re.sub(
        r"(?<![A-Za-z0-9])sk-(?:proj-|or-v1-)?[A-Za-z0-9_-]{16,}",
        "[REDACTED]",
        value,
    )


def validate_preregistration(
    path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], Path, Path, Path]:
    preregistration = read_json(path)
    artifacts = preregistration["frozen_artifacts"]
    case_file = WORKSPACE_ROOT / artifacts["case_file"]["path"]
    config_path = WORKSPACE_ROOT / artifacts["config"]["path"]
    protocol_path = WORKSPACE_ROOT / artifacts["protocol"]["path"]
    records = read_jsonl(case_file)
    expected = {
        artifacts["case_file"]["path"]: artifacts["case_file"]["sha256"],
        artifacts["config"]["path"]: artifacts["config"]["sha256"],
        artifacts["protocol"]["path"]: artifacts["protocol"]["sha256"],
        **artifacts["method_sources"],
        **artifacts.get("execution_sources", {}),
    }
    mismatches = {
        relative: {
            "expected": digest,
            "actual": sha256_file(WORKSPACE_ROOT / relative),
        }
        for relative, digest in expected.items()
        if sha256_file(WORKSPACE_ROOT / relative) != digest
    }
    if mismatches:
        raise RuntimeError(f"Frozen discovery source mismatch: {mismatches}")
    frozen_ids = [item["case_id"] for item in preregistration["selection"]["selected"]]
    if [item["case_id"] for item in records] != frozen_ids:
        raise RuntimeError("Discovery case order differs from preregistration")
    return preregistration, records, case_file, config_path, protocol_path


def require_credentials() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY must be injected through the environment")
    base_url = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
    if base_url != OPENROUTER_BASE_URL:
        raise RuntimeError(
            f"OPENAI_BASE_URL must equal the frozen provider endpoint {OPENROUTER_BASE_URL}"
        )


def command_for(
    attempt: dict[str, Any],
    preregistration: dict[str, Any],
    case_file: Path,
    config_path: Path,
    protocol_path: Path,
) -> list[str]:
    condition = attempt["condition"]
    definitions = {
        item["condition"]: item for item in preregistration["paired_conditions"]
    }
    definition = definitions[condition]
    execution = preregistration["execution"]
    return [
        sys.executable,
        str(WORKSPACE_ROOT / "experiments/run_case.py"),
        "--case-file", str(case_file),
        "--case-id", attempt["case_id"],
        "--run-id", attempt["run_id"],
        "--runner", definition["runner"],
        "--method", definition["method"],
        "--model", execution["model"],
        "--seed", str(execution["seed"]),
        "--config", str(config_path),
        "--protocol", str(protocol_path),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, default=PREREGISTRATION)
    args = parser.parse_args()
    preregistration_path = args.preregistration.resolve()
    preregistration, records, case_file, config_path, protocol_path = (
        validate_preregistration(preregistration_path)
    )
    require_credentials()
    config = load_harness_config(config_path, WORKSPACE_ROOT)
    execution = preregistration["execution"]
    run_ids = execution.get("run_ids", RUN_IDS)
    schedule = build_schedule(records, run_ids)
    coordinator_root = config.runs_root / execution.get(
        "coordinator_run_id", "envsolve-v0-discovery5-r1-paired"
    )
    coordinator_root.mkdir(parents=True, exist_ok=True)
    summary_path = coordinator_root / "execution_summary.json"
    prior = read_json(summary_path) if summary_path.is_file() else {}
    results_by_key = {
        (item["case_id"], item["condition"]): item
        for item in prior.get("attempts", [])
    }
    controller = BatchProcessController()
    active_attempt: dict[str, Any] | None = None
    previous_sigint = signal.getsignal(signal.SIGINT)
    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def terminate(signum: int, _frame: Any) -> None:
        controller.cancel(f"paired discovery interrupted by signal {signum}")
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, terminate)
    signal.signal(signal.SIGTERM, terminate)
    interrupted = False
    try:
        for attempt in schedule:
            key = (attempt["case_id"], attempt["condition"])
            case_root = (
                config.runs_root
                / safe_name(attempt["run_id"])
                / safe_name(attempt["case_id"])
            )
            if case_root.exists() and any(case_root.iterdir()):
                results_by_key.setdefault(
                    key,
                    {**attempt, "state": "existing_first_attempt", "process_exit_code": None},
                )
                continue
            command = command_for(
                attempt,
                preregistration,
                case_file,
                config_path,
                protocol_path,
            )
            active_attempt = attempt
            process = subprocess.Popen(
                command,
                cwd=WORKSPACE_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            controller.register(attempt["case_id"], process)
            try:
                stdout, stderr = process.communicate()
            finally:
                controller.unregister(attempt["case_id"])
            active_attempt = None
            results_by_key[key] = {
                **attempt,
                "state": "process_finished",
                "process_exit_code": process.returncode,
                "stdout": _redact(stdout),
                "stderr": _redact(stderr),
            }
            write_json(
                summary_path,
                {
                    "schema_version": "1.0.0",
                    "preregistration": str(preregistration_path.relative_to(WORKSPACE_ROOT)),
                    "attempts": [
                        results_by_key[key]
                        for item in schedule
                        if (key := (item["case_id"], item["condition"])) in results_by_key
                    ],
                    "complete": len(results_by_key) == len(schedule),
                    "interrupted": False,
                },
            )
            print(
                f"case={attempt['case_id']} condition={attempt['condition']} "
                f"exit={process.returncode}",
                flush=True,
            )
    except KeyboardInterrupt:
        interrupted = True
        if active_attempt is not None:
            case_root = (
                config.runs_root
                / safe_name(active_attempt["run_id"])
                / safe_name(active_attempt["case_id"])
            )
            cleaned = cleanup_case_containers(case_root)
            mark_case_interrupted(case_root, controller.reason or "interrupted", None, cleaned)
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
        write_json(
            summary_path,
            {
                "schema_version": "1.0.0",
                "preregistration": str(preregistration_path.relative_to(WORKSPACE_ROOT)),
                "attempts": [
                    results_by_key[key]
                    for item in schedule
                    if (key := (item["case_id"], item["condition"])) in results_by_key
                ],
                "complete": len(results_by_key) == len(schedule),
                "interrupted": interrupted,
            },
        )
    if interrupted:
        return 130
    failed = sum(
        item.get("process_exit_code") not in (None, 0)
        for item in results_by_key.values()
    )
    print(f"summary={summary_path}")
    print(f"attempts={len(results_by_key)} failed_processes={failed}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"preflight_error={exc}", file=sys.stderr)
        raise SystemExit(2)
