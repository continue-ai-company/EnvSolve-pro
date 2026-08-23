from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from envsolve_harness.core.io import read_json
from envsolve_harness.results import summarize_schedule as summarize_schedule_v1
from envsolve_harness.utils.provenance import sha256_file


def _elapsed_seconds(metadata: dict[str, Any]) -> float | None:
    started_at = metadata.get("started_at")
    finished_at = metadata.get("finished_at")
    if not isinstance(started_at, str) or not isinstance(finished_at, str):
        return None
    try:
        return (
            datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
            - datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        ).total_seconds()
    except ValueError:
        return None


def _trajectory_resources(root: Path) -> dict[str, int] | None:
    path = root / "generation" / "trajectory.jsonl"
    if not path.is_file():
        return None
    request_indexes: set[int] = set()
    completed_request_indexes: set[int] = set()
    errored_request_indexes: set[int] = set()
    provider_attempts = 0
    provider_errors = 0
    input_tokens = 0
    output_tokens = 0
    cached_input_tokens = 0
    reasoning_output_tokens = 0
    commands = 0
    successful_commands = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("event") == "provider_response":
            provider_attempts += 1
            request_index = event.get("request_index")
            if isinstance(request_index, int):
                request_indexes.add(request_index)
                completed_request_indexes.add(request_index)
            usage = (event.get("response") or {}).get("usage") or {}
            input_tokens += int(usage.get("prompt_tokens") or 0)
            output_tokens += int(usage.get("completion_tokens") or 0)
            prompt_details = usage.get("prompt_tokens_details") or {}
            completion_details = usage.get("completion_tokens_details") or {}
            cached_input_tokens += int(prompt_details.get("cached_tokens") or 0)
            reasoning_output_tokens += int(completion_details.get("reasoning_tokens") or 0)
        elif event.get("event") == "provider_error":
            provider_attempts += 1
            provider_errors += 1
            request_index = event.get("request_index")
            if isinstance(request_index, int):
                request_indexes.add(request_index)
                errored_request_indexes.add(request_index)
        elif event.get("event") == "tool_result":
            commands += 1
            result = event.get("result") or {}
            successful_commands += result.get("exit_code") == 0
    if not request_indexes and commands == 0:
        return None
    return {
        "requests_started": len(request_indexes),
        "provider_attempts_started": provider_attempts,
        "provider_retries": provider_errors,
        "provider_retry_recoveries": len(
            completed_request_indexes & errored_request_indexes
        ),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cached_input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "reasoning_output_tokens": reasoning_output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "commands": commands,
        "successful_commands": successful_commands,
    }


def _generation_result_resources(root: Path) -> dict[str, Any] | None:
    path = root / "generation" / "result.json"
    if not path.is_file():
        return None
    metadata = read_json(path).get("metadata") or {}
    if not isinstance(metadata, dict):
        return None

    agent_policy = metadata.get("agent_policy") or {}
    trace = metadata.get("container_command_trace") or {}
    execution_budget = metadata.get("execution_budget") or {}
    if not isinstance(agent_policy, dict):
        agent_policy = {}
    if not isinstance(trace, dict):
        trace = {}
    if not isinstance(execution_budget, dict):
        execution_budget = {}
    budget_usage = execution_budget.get("usage") or {}
    if not isinstance(budget_usage, dict):
        budget_usage = {}
    token_usage = metadata.get("token_usage") or agent_policy.get("token_usage") or {}
    if not isinstance(token_usage, dict):
        token_usage = {}

    commands = trace.get("count")
    successful_commands = trace.get("successful_count")
    if commands is None:
        commands = agent_policy.get("container_command_count")
        rounds = agent_policy.get("rounds") or []
        round_successes = [
            item.get("successful_container_command_count")
            for item in rounds
            if isinstance(item, dict)
            and isinstance(item.get("successful_container_command_count"), int)
        ]
        successful_commands = sum(round_successes) if round_successes else None

    elapsed = budget_usage.get("elapsed_wall_clock_seconds")
    if elapsed is None:
        elapsed = _elapsed_seconds(metadata)
    if not any((token_usage, budget_usage, commands is not None, elapsed is not None)):
        return None

    input_tokens = token_usage.get("input_tokens")
    output_tokens = token_usage.get("output_tokens")
    total_tokens = token_usage.get("total_tokens")
    if (
        total_tokens is None
        and isinstance(input_tokens, int)
        and isinstance(output_tokens, int)
    ):
        total_tokens = input_tokens + output_tokens
    cached_input_tokens = token_usage.get(
        "cached_input_tokens",
        token_usage.get("cache_read_tokens"),
    )
    resources = {
        "candidates": budget_usage.get("candidates"),
        "requests_started": None,
        "provider_retries": None,
        "provider_retry_recoveries": None,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cached_input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "cache_write_input_tokens": token_usage.get("cache_write_input_tokens"),
        "reasoning_output_tokens": token_usage.get("reasoning_output_tokens"),
        "total_tokens": total_tokens,
        "environments": budget_usage.get("environments"),
        "commands": commands,
        "successful_commands": successful_commands,
        "budget_commands": budget_usage.get("commands"),
        "rounds_started": agent_policy.get("rounds_started"),
        "elapsed_wall_clock_seconds": elapsed,
        "elapsed_scope": "generation",
        "provider_attempts_started": None,
        "provider_attempts_in_progress": None,
        "source": "generation/result.json",
    }
    trajectory = _trajectory_resources(root)
    if trajectory is not None:
        for key, value in trajectory.items():
            if resources.get(key) is None:
                resources[key] = value
        resources["source"] = "generation/result.json+trajectory.jsonl"
    return resources


def _paired_aggregate_v2(
    runs: list[dict[str, Any]],
    treatment_method: str,
    control_method: str,
    *,
    missing_official_as_failure: bool,
) -> dict[str, int]:
    pairs: dict[int | str, dict[str, dict[str, Any]]] = {}
    for run in runs:
        pair_key = run.get("pair_index")
        if not isinstance(pair_key, int):
            pair_key = run.get("pair_id")
        if not isinstance(pair_key, (int, str)) or pair_key == "":
            continue
        methods = pairs.setdefault(pair_key, {})
        method = str(run["method"])
        if method in methods:
            raise ValueError(f"Pair {pair_key} repeats method {method!r}")
        methods[method] = run

    counts = {
        "pairs": len(pairs),
        "eligible_pairs": 0,
        "censored_pairs": 0,
        "treatment_only_pass": 0,
        "control_only_pass": 0,
        "both_pass": 0,
        "neither_pass": 0,
    }
    for pair_key, methods in pairs.items():
        if treatment_method not in methods or control_method not in methods:
            raise ValueError(f"Pair {pair_key} lacks a treatment or control episode")
        treatment = methods[treatment_method]
        control = methods[control_method]
        eligible = treatment["scientifically_eligible"] and control["scientifically_eligible"]
        if not missing_official_as_failure:
            eligible = (
                eligible
                and isinstance(treatment["official_pass"], bool)
                and isinstance(control["official_pass"], bool)
            )
        if not eligible:
            counts["censored_pairs"] += 1
            continue
        counts["eligible_pairs"] += 1
        treatment_pass = treatment["official_pass"] is True
        control_pass = control["official_pass"] is True
        if treatment_pass and control_pass:
            counts["both_pass"] += 1
        elif treatment_pass:
            counts["treatment_only_pass"] += 1
        elif control_pass:
            counts["control_only_pass"] += 1
        else:
            counts["neither_pass"] += 1
    return counts


def summarize_schedule(
    schedule_path: Path,
    runs_root: Path,
    *,
    treatment_method: str | None = None,
    control_method: str | None = None,
) -> dict[str, Any]:
    summary = summarize_schedule_v1(
        schedule_path,
        runs_root,
        treatment_method=treatment_method,
        control_method=control_method,
    )
    schedule = read_json(schedule_path.resolve())
    episodes = schedule.get("episodes") or []
    episode_by_run_id = {
        episode.get("run_id"): episode
        for episode in episodes
        if isinstance(episode, dict) and isinstance(episode.get("run_id"), str)
    }
    resolved_runs_root = runs_root.resolve()
    for run in summary["runs"]:
        episode = episode_by_run_id.get(run.get("run_id")) or {}
        if isinstance(episode.get("pair_id"), str):
            run["pair_id"] = episode["pair_id"]
        resources = run.get("resources")
        if isinstance(resources, dict):
            run["resources"] = {
                **resources,
                "source": "generation/budget_ledger.json",
            }
            continue
        artifact_root = resolved_runs_root / str(run["artifact_root"])
        run["resources"] = _generation_result_resources(artifact_root)
    if treatment_method is not None and control_method is not None:
        summary["paired_scientific"] = {
            "treatment_method": treatment_method,
            "control_method": control_method,
            **_paired_aggregate_v2(
                summary["runs"],
                treatment_method,
                control_method,
                missing_official_as_failure=False,
            ),
        }
        summary["paired_end_to_end_scientific"] = {
            "treatment_method": treatment_method,
            "control_method": control_method,
            "missing_official_result": "deployment_failure",
            **_paired_aggregate_v2(
                summary["runs"],
                treatment_method,
                control_method,
                missing_official_as_failure=True,
            ),
        }
    summary["schema_version"] = "1.1.0"
    summary["resource_schema_version"] = "2.0.0"
    project_root = Path(__file__).resolve().parents[1]
    summary["analysis_implementation"] = {
        "summarizer": {
            "path": "envsolve_harness/results_v2.py",
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "frozen_base_summarizer": {
            "path": "envsolve_harness/results.py",
            "sha256": sha256_file(project_root / "envsolve_harness" / "results.py"),
        },
    }
    return summary
