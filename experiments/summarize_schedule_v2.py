#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.results_v2 import summarize_schedule
from envsolve_harness.utils.provenance import sha256_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit and summarize a frozen schedule with v2 resource support."
    )
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, default=ROOT / "runs")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--progress",
        type=Path,
        action="append",
        default=[],
        help="Coordinator progress file; repeat to combine an amended execution.",
    )
    parser.add_argument("--treatment-method")
    parser.add_argument("--control-method")
    return parser.parse_args()


def _project_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def _attach_coordinator_progress(
    summary: dict[str, Any],
    progress_paths: list[Path],
) -> None:
    expected = {
        (run["position"], run["run_id"]): run
        for run in summary["runs"]
    }
    selected: dict[tuple[Any, Any], dict[str, Any]] = {}
    sources = []
    for path in progress_paths:
        resolved = path.resolve()
        progress = read_json(resolved)
        outcomes = progress.get("outcomes")
        if not isinstance(outcomes, list):
            raise ValueError(f"Progress file has no outcome list: {resolved}")
        sources.append(
            {
                "path": _project_path(resolved),
                "sha256": sha256_file(resolved),
            }
        )
        for outcome in outcomes:
            if not isinstance(outcome, dict):
                continue
            key = (outcome.get("position"), outcome.get("run_id"))
            expected_run = expected.get(key)
            if expected_run is None:
                continue
            if key in selected:
                raise ValueError(f"Duplicate progress outcome for schedule run: {key}")
            for field in ("case_id", "method", "seed"):
                if outcome.get(field) != expected_run.get(field):
                    raise ValueError(
                        f"Progress {field} does not match schedule for run {key}"
                    )
            selected[key] = {
                field: outcome.get(field)
                for field in (
                    "position",
                    "case_id",
                    "run_id",
                    "method",
                    "seed",
                    "state",
                    "process_exit_code",
                    "started_at",
                    "finished_at",
                    "duration_seconds",
                )
            }
    missing = sorted(set(expected) - set(selected))
    if missing:
        raise ValueError(f"Coordinator progress is missing schedule runs: {missing}")

    runs = sorted(selected.values(), key=lambda item: int(item["position"]))
    by_method: dict[str, dict[str, Any]] = {}
    for run in runs:
        method = str(run["method"])
        aggregate = by_method.setdefault(
            method,
            {
                "runs": 0,
                "process_finished": 0,
                "endpoint_wall_clock_seconds": 0.0,
            },
        )
        aggregate["runs"] += 1
        aggregate["process_finished"] += run["state"] == "process_finished"
        duration = run["duration_seconds"]
        if not isinstance(duration, (int, float)):
            raise ValueError(f"Progress duration is unavailable for {run['run_id']}")
        aggregate["endpoint_wall_clock_seconds"] += duration

    summary["coordinator_progress"] = {
        "sources": sources,
        "runs": runs,
        "aggregate_by_method": by_method,
    }


def main() -> int:
    args = parse_args()
    summary = summarize_schedule(
        args.schedule,
        args.runs_root,
        treatment_method=args.treatment_method,
        control_method=args.control_method,
    )
    if args.progress:
        _attach_coordinator_progress(summary, args.progress)
    summary["analysis_implementation"]["cli"] = {
        "path": _project_path(Path(__file__)),
        "sha256": sha256_file(Path(__file__).resolve()),
    }
    write_json(args.output, summary)
    print(f"summary={args.output.resolve()}")
    print(
        f"runs={summary['descriptive']['runs']} "
        f"artifact_valid={summary['descriptive']['artifact_integrity_valid']} "
        f"scientifically_eligible={summary['scientific']['eligible_runs']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
