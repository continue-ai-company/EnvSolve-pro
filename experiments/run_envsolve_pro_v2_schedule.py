#!/usr/bin/env python3
from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path
import signal
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.config import load_harness_config
from envsolve_harness.execution.batch import cleanup_case_containers, mark_case_interrupted
from envsolve_harness.execution.schedule import ScheduleProgress, run_scheduled_process
from envsolve_harness.runners.openrouter_agent import provider_connection
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.utils.provenance import sha256_file
from experiments.run_schedule import (
    _episode_identity,
    _validate_schedule,
    parse_args,
)


PROVIDER_API_RUNNERS = frozenset(
    {
        "deepseek-repository-agent",
        "deepseek-goal-aware-agent",
        "deepseek-free-agent",
        "envsolve-pro-v2-atomic",
        "envsolve-pro-v2-atomic-handoff",
        "envsolve-pro-v2",
        "envsolve-pro-v2-incumbent",
        "envsolve-pro-v2-current-goal",
        "envsolve-pro-v2-ledger",
        "envsolve-pro-v2-scheduled-observation",
        "envsolve-pro-v2-verifier-handoff",
        "envsolve-pro-v2-stateful-replay",
        "envsolve-pro-v2-incremental-program",
        "envsolve-pro-v2-incremental-program-annotated",
        "envsolve-pro-v2-incremental-program-editable",
    }
)
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _validate_provider_environment(
    identities: Sequence[dict[str, object]],
    environ: Mapping[str, str] | None = None,
) -> None:
    environment = os.environ if environ is None else environ
    missing = sorted(
        {
            provider_connection(str(identity.get("model", "")))[
                "credential_variable"
            ]
            for identity in identities
            if str(identity["runner"]) in PROVIDER_API_RUNNERS
            and not environment.get(
                provider_connection(str(identity.get("model", "")))[
                    "credential_variable"
                ],
                "",
            ).strip()
        }
    )
    if missing:
        raise RuntimeError(
            f"{', '.join(missing)} required by pending EnvSolve-Pro V2 episodes; "
            "no schedule progress was recorded"
        )


def _provider_execution_metadata(
    identities: Sequence[dict[str, object]],
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    provider_identities = [
        identity
        for identity in identities
        if str(identity["runner"]) in PROVIDER_API_RUNNERS
    ]
    provider_backed = bool(provider_identities)
    if not provider_backed:
        return {"provider_backed": False}
    environment = os.environ if environ is None else environ
    connections = {
        tuple(sorted(provider_connection(str(identity.get("model", ""))).items()))
        for identity in provider_identities
    }
    routes = [dict(items) for items in sorted(connections)]
    provider_order = [
        item.strip()
        for item in environment.get("OPENROUTER_PROVIDER_ORDER", "").split(",")
        if item.strip()
    ]
    if len(routes) == 1 and routes[0]["provider"] == "openrouter":
        return {
            "provider_backed": True,
            "credential_variable": "OPENROUTER_API_KEY",
            "base_url": OPENROUTER_BASE_URL,
            "provider_order": provider_order,
        }
    if len(routes) == 1:
        return {"provider_backed": True, **routes[0]}
    return {
        "provider_backed": True,
        "routes": routes,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.start_position < 1:
        raise ValueError("--start-position must be positive")
    if args.stop_position is not None and args.stop_position < args.start_position:
        raise ValueError("--stop-position must be at least --start-position")

    schedule_path = args.schedule.resolve()
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    _validate_schedule(schedule_path, schedule)
    config = load_harness_config(args.config.resolve(), ROOT)
    case_file = ROOT / str(schedule["case_file"])
    progress_path = (
        args.progress.resolve()
        if args.progress is not None
        else ROOT / "experiments/runs" / f"{schedule_path.stem}-progress.json"
    )
    timeout_seconds = float(
        schedule.get(
            "episode_timeout_seconds",
            config.generation_timeout + config.evaluation_process_timeout + 600,
        )
    )
    selected_identities = [
        _episode_identity(episode, schedule, args.runner)
        for episode in schedule["episodes"]
        if args.start_position <= int(episode["position"])
        and (args.stop_position is None or int(episode["position"]) <= args.stop_position)
    ]
    progress = ScheduleProgress(
        progress_path,
        schedule_path,
        sha256_file(schedule_path),
        execution={
            "runner": args.runner,
            "episode_runner_override": any(
                "runner" in episode for episode in schedule["episodes"]
            ),
            "config": str(args.config.resolve()),
            "config_sha256": sha256_file(args.config.resolve()),
            "protocol": str(args.protocol.resolve()),
            "protocol_sha256": sha256_file(args.protocol.resolve()),
            "episode_timeout_seconds": timeout_seconds,
            "timeout_source": (
                "schedule" if "episode_timeout_seconds" in schedule else "derived_from_config"
            ),
            "provider": _provider_execution_metadata(selected_identities),
        },
    )
    pending = [
        identity
        for identity in selected_identities
        if not progress.contains(int(identity["position"]))
    ]
    _validate_provider_environment(pending)
    for position in progress.recover_orphans():
        print(f"position={position} state=orphaned", flush=True)

    interrupted = False
    for episode in schedule["episodes"]:
        position = int(episode["position"])
        if position < args.start_position:
            continue
        if args.stop_position is not None and position > args.stop_position:
            break
        if progress.contains(position):
            print(f"position={position} state=already-recorded", flush=True)
            continue
        identity = _episode_identity(episode, schedule, args.runner)
        progress.begin(identity)
        command = [
            sys.executable,
            str(ROOT / "experiments/run_envsolve_pro_v2_case.py"),
            "--case-file", str(case_file),
            "--case-id", identity["case_id"],
            "--run-id", identity["run_id"],
            "--runner", identity["runner"],
            "--method", identity["method"],
            "--model", identity["model"],
            "--config", str(args.config.resolve()),
            "--protocol", str(args.protocol.resolve()),
        ]
        if identity["seed"] is not None:
            command.extend(["--seed", str(identity["seed"])])
        print(
            f"position={position} case={identity['case_id']} "
            f"runner={identity['runner']} method={identity['method']}",
            flush=True,
        )
        previous_sigterm = signal.getsignal(signal.SIGTERM)

        def interrupt_episode(_signal_number: int, _frame: object) -> None:
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, interrupt_episode)
        try:
            outcome = run_scheduled_process(
                command,
                cwd=ROOT,
                timeout_seconds=timeout_seconds,
            )
        finally:
            signal.signal(signal.SIGTERM, previous_sigterm)
        case_root = config.runs_root / safe_name(identity["run_id"]) / safe_name(
            identity["case_id"]
        )
        outcome["artifact_root"] = str(case_root.resolve())
        if outcome["state"] in {"timed_out", "interrupted"}:
            cleaned = cleanup_case_containers(case_root)
            outcome["cleaned_container_ids"] = list(cleaned)
            outcome["artifact_interruption_recorded"] = mark_case_interrupted(
                case_root,
                str(outcome["reason"]),
                outcome["process_exit_code"],
                cleaned,
            )
        progress.complete(position, outcome)
        print(
            f"position={position} state={outcome['state']} "
            f"process_exit_code={outcome['process_exit_code']}",
            flush=True,
        )
        if outcome["state"] == "interrupted":
            interrupted = True
            break

    failed = any(
        item.get("state") != "process_finished"
        or item.get("process_exit_code") != 0
        for item in progress.outcomes
        if args.start_position <= int(item["position"])
        and (args.stop_position is None or int(item["position"]) <= args.stop_position)
    )
    print(f"progress={progress_path}")
    if interrupted:
        return 130
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
