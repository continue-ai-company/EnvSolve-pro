#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve.integrations import ingest_shell_command_trace
from envsolve.solver import SolverStateSession
from envsolve.state import audit_state_artifacts
from envsolve_harness.scripts.replay_actions import analyze_successful_command


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"JSONL line {line_number} is not an object")
        records.append(value)
    return records


def _commands(records: list[dict], trace_format: str) -> list[dict]:
    if trace_format == "command-jsonl":
        return records
    if not records or records[-1].get("node") != "commands_history":
        raise ValueError("EnvBench trace does not end with commands_history")
    commands = records[-1].get("commands")
    if isinstance(commands, str):
        commands = json.loads(commands)
    if not isinstance(commands, list) or not all(isinstance(item, dict) for item in commands):
        raise ValueError("commands_history.commands must be a list of objects")
    return commands


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import a recorded shell trajectory into the EnvSolve state protocol."
    )
    parser.add_argument("--case-json", type=Path, required=True)
    parser.add_argument("--trace-jsonl", type=Path, required=True)
    parser.add_argument(
        "--trace-format",
        choices=("command-jsonl", "envbench-commands-history"),
        default="command-jsonl",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--project-directory")
    args = parser.parse_args()

    case_path = args.case_json.resolve()
    trace_path = args.trace_jsonl.resolve()
    output_dir = args.output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"State import output already exists: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    event_log = output_dir / "state.jsonl"
    snapshot_path = output_dir / "snapshot.json"
    audit_path = output_dir / "audit.json"
    summary_path = output_dir / "import_summary.json"

    case = _read_json(case_path)
    if not isinstance(case, dict):
        raise ValueError("Case input must be a JSON object")
    trace_records = _read_jsonl(trace_path)
    commands = _commands(trace_records, args.trace_format)
    trace_sha256 = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    session = SolverStateSession(event_log, snapshot_path, case)
    session.profile_repository(
        {
            "repository": case.get("repository"),
            "revision": case.get("revision"),
            "trace_format": args.trace_format,
            "trace_source": args.source,
            "trace_sha256": trace_sha256,
        }
    )
    summary = ingest_shell_command_trace(
        session,
        commands,
        source=args.source,
        analyzer=analyze_successful_command,
        project_directory=args.project_directory,
    )
    audit = audit_state_artifacts(event_log, snapshot_path, str(case["case_id"]))
    audit_path.write_text(json.dumps(audit.to_dict(), indent=2, sort_keys=True) + "\n")
    result = {
        "schema_version": "1.0.0",
        "case_id": case["case_id"],
        "trace_path": str(trace_path),
        "trace_sha256": trace_sha256,
        "trace_format": args.trace_format,
        "source": args.source,
        "commands": summary.to_dict(),
        "event_count": audit.event_count,
        "snapshot_hash": audit.snapshot_hash,
        "audit_valid": audit.valid,
    }
    summary_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if audit.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
