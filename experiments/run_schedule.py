#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path
import signal
import sys
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve_harness.core.config import load_harness_config
from envsolve_harness.core.models import HarnessConfig
from envsolve_harness.execution.batch import cleanup_case_containers, mark_case_interrupted
from envsolve_harness.execution.schedule import ScheduleProgress, run_scheduled_process
from envsolve_harness.storage.artifacts import safe_name
from envsolve_harness.utils.provenance import sha256_file


OPENAI_API_RUNNERS = frozenset(
    {
        "envbench-agent",
        "envsolve",
        "envsolve-v0",
        "repo2run",
    }
)
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
_PROVIDER_BASE_URL_BY_PRICING_HOST = {
    "openrouter.ai": OPENROUTER_BASE_URL,
    "api-docs.deepseek.com": DEEPSEEK_BASE_URL,
    "api.deepseek.com": DEEPSEEK_BASE_URL,
}


def parse_args(
    argv: Sequence[str] | None = None,
    *,
    default_schedule: Path | None = None,
    default_progress: Path | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a frozen sequential experiment schedule.")
    parser.add_argument("--schedule", type=Path, default=default_schedule, required=default_schedule is None)
    parser.add_argument("--progress", type=Path, default=default_progress)
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
    parser.add_argument("--runner", default="envsolve")
    parser.add_argument("--start-position", type=int, default=1)
    parser.add_argument("--stop-position", type=int)
    return parser.parse_args(argv)


def _validate_schedule(schedule_path: Path, schedule: dict[str, object]) -> None:
    episodes = schedule.get("episodes")
    if schedule.get("schema_version") != "1.0.0" or not isinstance(episodes, list):
        raise ValueError("Unsupported schedule schema")
    positions = [int(item["position"]) for item in episodes]
    if positions != list(range(1, len(episodes) + 1)):
        raise ValueError("Schedule positions must be contiguous and ordered from one")
    run_ids = [str(item["run_id"]) for item in episodes]
    if len(run_ids) != len(set(run_ids)):
        raise ValueError("Schedule run_id values must be unique")
    case_file = ROOT / str(schedule["case_file"])
    expected_case_hash = schedule.get("case_file_sha256")
    if not case_file.is_file() or sha256_file(case_file) != expected_case_hash:
        raise ValueError(f"Schedule case file hash mismatch: {schedule_path}")


def _episode_identity(
    episode: dict[str, object],
    schedule: dict[str, object],
    default_runner: str,
) -> dict[str, object]:
    runner = str(episode.get("runner", default_runner)).strip()
    model = str(episode.get("model", schedule.get("model", ""))).strip()
    if not runner:
        raise ValueError("Schedule episode runner cannot be empty")
    if not model:
        raise ValueError("Schedule episode model cannot be empty")
    raw_seed = episode.get("seed")
    return {
        "position": int(episode["position"]),
        "case_id": str(episode["case_id"]),
        "run_id": str(episode["run_id"]),
        "runner": runner,
        "method": str(episode["method"]),
        "model": model,
        "seed": int(raw_seed) if raw_seed is not None else None,
    }


def _expected_provider_base_url(
    config: HarnessConfig,
    model: str,
) -> str | None:
    pricing = config.model_pricing.get(model)
    if pricing is None or not pricing.source_url:
        return None
    host = urlparse(pricing.source_url).netloc.lower()
    return _PROVIDER_BASE_URL_BY_PRICING_HOST.get(host)


def _validate_provider_environment(
    identities: Sequence[dict[str, object]],
    config: HarnessConfig,
    environ: Mapping[str, str] | None = None,
) -> None:
    provider_episodes = [
        identity
        for identity in identities
        if str(identity["runner"]) in OPENAI_API_RUNNERS
    ]
    if not provider_episodes:
        return
    environment = os.environ if environ is None else environ
    if not environment.get("OPENAI_API_KEY", "").strip():
        raise RuntimeError(
            "OPENAI_API_KEY is required by pending provider-backed episodes; "
            "no schedule progress was recorded"
        )
    actual_base_url = environment.get("OPENAI_BASE_URL", "").rstrip("/")
    expected_routes: dict[str, list[str]] = {}
    for identity in provider_episodes:
        model = str(identity["model"])
        expected = _expected_provider_base_url(config, model)
        if expected is not None:
            expected_routes.setdefault(expected, []).append(model)
    for expected, models in sorted(expected_routes.items()):
        if actual_base_url == expected:
            continue
        raise RuntimeError(
            f"OPENAI_BASE_URL must equal {expected!r} for provider-backed "
            f"model(s) {', '.join(sorted(set(models)))}; "
            "no schedule progress was recorded"
        )


def _provider_execution_metadata(
    identities: Sequence[dict[str, object]],
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    provider_backed = any(
        str(identity["runner"]) in OPENAI_API_RUNNERS
        for identity in identities
    )
    if not provider_backed:
        return {"provider_backed": False}
    environment = os.environ if environ is None else environ
    base_url = environment.get("OPENAI_BASE_URL", "").rstrip("/")
    return {
        "provider_backed": True,
        "credential_variable": "OPENAI_API_KEY",
        "base_url": base_url or None,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    default_schedule: Path | None = None,
    default_progress: Path | None = None,
) -> int:
    args = parse_args(
        argv,
        default_schedule=default_schedule,
        default_progress=default_progress,
    )
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
        else (ROOT / "experiments/runs" / f"{schedule_path.stem}-progress.json")
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
    pending_identities = [
        identity
        for identity in selected_identities
        if not progress.contains(int(identity["position"]))
    ]
    _validate_provider_environment(pending_identities, config)
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
            str(ROOT / "experiments/run_case.py"),
            "--case-file", str(case_file),
            "--case-id", identity["case_id"],
            "--run-id", identity["run_id"],
            "--runner", str(identity["runner"]),
            "--method", identity["method"],
            "--model", str(identity["model"]),
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
        case_root = (
            config.runs_root
            / safe_name(identity["run_id"])
            / safe_name(identity["case_id"])
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
