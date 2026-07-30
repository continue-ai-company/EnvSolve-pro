from __future__ import annotations

from datetime import datetime
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
    return {
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
    resolved_runs_root = runs_root.resolve()
    for run in summary["runs"]:
        resources = run.get("resources")
        if isinstance(resources, dict):
            run["resources"] = {
                **resources,
                "source": "generation/budget_ledger.json",
            }
            continue
        artifact_root = resolved_runs_root / str(run["artifact_root"])
        run["resources"] = _generation_result_resources(artifact_root)
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
