from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
from typing import Any

from envsolve_harness.scripts.replay_actions import ReplayAction, analyze_successful_command


@dataclass(frozen=True)
class TrajectoryDistillationResult:
    script: str
    kept_commands: tuple[str, ...]
    dropped_commands: tuple[str, ...]
    unknown_commands: tuple[str, ...]
    actions: tuple[ReplayAction, ...] = ()


def distill_envbench_commands(
    commands: list[dict[str, Any]],
    project_directory: str | None = None,
) -> TrajectoryDistillationResult:
    replay: list[str] = []
    actions: list[ReplayAction] = []
    kept: list[str] = []
    dropped: list[str] = []
    unknown: list[str] = []

    for record in commands:
        command = str(record.get("command", "")).strip()
        if not command:
            continue
        if record.get("exit_code") != 0:
            dropped.append(command)
            continue
        analysis = analyze_successful_command(command, project_directory)
        if analysis.unsupported_reason:
            unknown.append(f"{command} [{analysis.unsupported_reason}]")
            continue
        if analysis.dropped:
            dropped.append(command)
            continue
        for action in analysis.actions:
            if action.command not in replay:
                replay.append(action.command)
                actions.append(action)
        kept.append(command)

    if project_directory and any("${PROJECT_ROOT}" in command for command in replay):
        replay.insert(0, 'PROJECT_ROOT="$(pwd)"')

    return TrajectoryDistillationResult(
        script="\n".join(replay) + ("\n" if replay else ""),
        kept_commands=tuple(kept),
        dropped_commands=tuple(dropped),
        unknown_commands=tuple(unknown),
        actions=tuple(actions),
    )


def commands_from_trajectory(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not records or records[-1].get("node") != "commands_history":
        raise ValueError("Trajectory does not end with a commands_history node")
    commands = records[-1].get("commands", [])
    if isinstance(commands, str):
        commands = json.loads(commands)
    if not isinstance(commands, list) or not all(isinstance(item, dict) for item in commands):
        raise ValueError("commands_history.commands must be a list of objects")
    return commands


def aggregate_token_usage(records: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, int] = defaultdict(int)
    input_details: dict[str, int] = defaultdict(int)
    output_details: dict[str, int] = defaultdict(int)
    requests = 0
    for record in records:
        messages = record.get("messages", [])
        if not isinstance(messages, list):
            continue
        for message in messages:
            if not isinstance(message, dict):
                continue
            content = message.get("message_content", {})
            usage = content.get("usage_metadata") if isinstance(content, dict) else None
            if not isinstance(usage, dict):
                continue
            requests += 1
            for name in ("input_tokens", "output_tokens", "total_tokens"):
                value = usage.get(name)
                if isinstance(value, int):
                    totals[name] += value
            for source_name, target in (
                ("input_token_details", input_details),
                ("output_token_details", output_details),
            ):
                details = usage.get(source_name)
                if isinstance(details, dict):
                    for name, value in details.items():
                        if isinstance(value, int):
                            target[str(name)] += value
    return {
        "requests": requests,
        **dict(totals),
        "input_token_details": dict(input_details),
        "output_token_details": dict(output_details),
    }
