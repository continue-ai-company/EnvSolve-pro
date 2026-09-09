#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ruff: noqa: E402 - load workspace modules after adding the repository root.

from envsolve_harness.codex.minimal_b_mcp import canonical_script
from envsolve_harness.core.config import load_harness_config
from envsolve_harness.core.io import read_json, write_json, write_text_atomic
from envsolve_harness.core.models import Case, RunSpec
from envsolve_harness.core.protocol import load_protocol
from envsolve_harness.runners.progress_agent import PROGRESS_METHODS
from envsolve_harness.runners.registry import RunnerOptions
from experiments.run_project_progress_case import _factory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one fixed M1b project lane using existing programs only."
    )
    parser.add_argument(
        "--schedule",
        type=Path,
        default=Path("experiments/schedules/envsolve_pro_m1b_artifact_replay_v1.json"),
    )
    parser.add_argument("--position", type=int, required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("runs/envsolve-pro-m1b-artifact-replay-v1"),
    )
    return parser.parse_args()


def _source_program(source: dict[str, Any], root: Path) -> str:
    path = root / str(source["path"])
    kind = source["kind"]
    if kind == "state-current-program":
        payload = read_json(path)
        program = payload.get("current_program")
        if not isinstance(program, str) or not program.strip():
            raise ValueError(f"state has no current_program: {path}")
        return canonical_script(program)
    if kind == "submitted-program":
        return canonical_script(path.read_text(encoding="utf-8"))
    raise ValueError(f"unsupported program source kind: {kind!r}")


def resolve_candidate(candidate: dict[str, Any], root: Path) -> str:
    sources = candidate.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError(f"candidate {candidate.get('candidate_id')!r} has no sources")
    programs = [_source_program(source, root) for source in sources]
    if any(program != programs[0] for program in programs[1:]):
        raise ValueError(
            f"candidate {candidate.get('candidate_id')!r} groups unequal programs"
        )
    return programs[0]


def validate_project(project: dict[str, Any], root: Path) -> dict[str, str]:
    candidates = project.get("candidates")
    rounds = project.get("rounds")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("project has no candidates")
    if not isinstance(rounds, list) or len(rounds) != 3:
        raise ValueError("M1b requires exactly three fixed rounds")

    programs: dict[str, str] = {}
    for candidate in candidates:
        candidate_id = str(candidate["candidate_id"])
        if candidate_id in programs:
            raise ValueError(f"duplicate candidate_id: {candidate_id}")
        programs[candidate_id] = resolve_candidate(candidate, root)

    expected = set(programs)
    for round_record in rounds:
        order = round_record.get("order")
        if not isinstance(order, list) or len(order) != len(set(order)):
            raise ValueError("each round must contain unique candidate IDs")
        if set(order) != expected:
            raise ValueError("each round must contain every physical candidate once")
    return programs


def _project(schedule: dict[str, Any], position: int) -> dict[str, Any]:
    matches = [
        project
        for project in schedule.get("projects", [])
        if project.get("position") == position
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one project at position {position}, found {len(matches)}")
    return matches[0]


def _configure_runner(schedule: dict[str, Any], project: dict[str, Any]) -> Any:
    shared = schedule["shared_configuration"]
    os.environ.update(
        {
            "ENVSOLVE_PROGRESS_ARM": "P",
            "ENVSOLVE_PROGRESS_STATE": str(ROOT / project["runner_state"]),
            "ENVSOLVE_PROGRESS_CONDITION_ID": str(project["condition_id"]),
            "ENVSOLVE_PROGRESS_PYTHON": str(project["python_version"]),
            "ENVSOLVE_PROGRESS_UPDATE_STATE": "0",
            "ENVSOLVE_REMOTE_DOCKER_TARGET": str(shared["execution_target"]),
            "ENVSOLVE_REMOTE_WORKSPACE_ROOT": str(shared["remote_workspace_root"]),
            "ENVSOLVE_REMOTE_EXPOSE_GPUS": (
                "1" if shared.get("expose_gpus") is True else "0"
            ),
        }
    )
    config = load_harness_config((ROOT / shared["config"]).resolve(), ROOT)
    protocol = load_protocol((ROOT / shared["protocol"]).resolve())
    run_spec = RunSpec(
        f"m1b-position{project['position']}-artifact-replay",
        PROGRESS_METHODS["P"],
        None,
        None,
    )
    return _factory(config, protocol, run_spec, RunnerOptions())


def main() -> int:
    args = parse_args()
    schedule_path = (ROOT / args.schedule).resolve()
    output_root = (ROOT / args.output_root).resolve()
    schedule = read_json(schedule_path)
    project = _project(schedule, args.position)
    programs = validate_project(project, ROOT)
    candidates = {
        str(candidate["candidate_id"]): candidate
        for candidate in project["candidates"]
    }
    lane_root = output_root / f"position{args.position}"
    inputs_root = lane_root / "inputs"
    for candidate_id, program in programs.items():
        write_text_atomic(inputs_root / f"{candidate_id}.sh", program + "\n")

    manifest = {
        "study_id": schedule["study_id"],
        "position": args.position,
        "case": project["case"],
        "target_condition": {
            "condition_id": project["condition_id"],
            "python_version": project["python_version"],
        },
        "fixed_rounds": project["rounds"],
        "physical_candidate_count": len(programs),
        "model_invoked": False,
        "state_updated": False,
        "cache_conditions": schedule["cache_conditions"],
        "program_sources": {
            candidate_id: candidate["sources"]
            for candidate_id, candidate in candidates.items()
        },
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(lane_root / "run-manifest.json", manifest)

    case = Case.from_dict(project["case"])
    runner = _configure_runner(schedule, project)
    setup_errors = 0
    sequence = 0
    for round_record in project["rounds"]:
        round_index = int(round_record["round"])
        for order_index, candidate_id in enumerate(round_record["order"], start=1):
            sequence += 1
            candidate = candidates[candidate_id]
            trial_root = (
                lane_root
                / f"round{round_index}"
                / f"{order_index:02d}-{candidate_id}"
            )
            started = time.monotonic()
            try:
                result = runner.replay_program(
                    case,
                    program=programs[candidate_id],
                    root=trial_root,
                )
            except Exception as exc:
                setup_errors += 1
                result = {
                    "status": "not_started",
                    "phase": "artifact-replay-setup",
                    "error": f"{type(exc).__name__}: {exc}",
                    "replay_wall_seconds": time.monotonic() - started,
                }
            result["m1b_artifact_replay"] = {
                "sequence": sequence,
                "round": round_index,
                "order_in_round": order_index,
                "candidate_id": candidate_id,
                "stage": candidate["stage"],
                "arm_aliases": candidate["arm_aliases"],
                "physical_measurement_count": 1,
                "model_invoked": False,
                "state_updated": False,
            }
            write_json(trial_root / "result.json", result)
            print(
                f"position={args.position} round={round_index} "
                f"candidate={candidate_id} status={result.get('status')}"
            )

    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    manifest["scheduled_physical_replays"] = sequence
    manifest["setup_error_count"] = setup_errors
    write_json(lane_root / "run-manifest.json", manifest)
    return 1 if setup_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
