from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

from envsolve_harness.scripts.replay_actions import analyze_successful_command


def _normalized_command(command: str) -> str:
    return " ".join(command.split())


def _normalized_output(output: str) -> str:
    return re.sub(r"\s+", " ", output).strip()


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _messages(records: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    calls: list[dict[str, Any]] = []
    outputs: dict[str, str] = {}
    for record in records:
        messages = record.get("messages")
        if not isinstance(messages, list):
            continue
        for message in messages:
            if not isinstance(message, dict):
                continue
            content = message.get("message_content")
            if not isinstance(content, dict):
                continue
            tool_calls = content.get("tool_calls")
            if isinstance(tool_calls, list):
                for call in tool_calls:
                    if not isinstance(call, dict):
                        continue
                    name = call.get("name")
                    if name not in (None, "execute_bash_command"):
                        continue
                    arguments = call.get("args")
                    if not isinstance(arguments, dict):
                        arguments = {}
                    calls.append(
                        {
                            "tool_call_id": str(call.get("id", "")),
                            "command": str(arguments.get("command", "")),
                            "reason": str(arguments.get("reason", "")),
                        }
                    )
            tool_call_id = content.get("tool_call_id")
            if isinstance(tool_call_id, str) and tool_call_id:
                outputs[tool_call_id] = str(content.get("content", ""))
    return calls, outputs


def _command_history(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not records or records[-1].get("node") != "commands_history":
        raise ValueError("trajectory does not end with commands_history")
    commands = records[-1].get("commands")
    if isinstance(commands, str):
        commands = json.loads(commands)
    if not isinstance(commands, list) or not all(isinstance(item, dict) for item in commands):
        raise ValueError("commands_history.commands must be a list of objects")
    return commands


def _action_class(command: str) -> str:
    analysis = analyze_successful_command(command)
    if analysis.actions:
        return "mutation"
    if analysis.dropped:
        return "observation"
    return "unsupported"


def analyze_trajectory_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    calls, outputs = _messages(records)
    history = _command_history(records)
    if len(calls) != len(history):
        raise ValueError("tool-call count does not match command history")

    prior_by_command: dict[str, list[dict[str, Any]]] = defaultdict(list)
    decisions = []
    for index, (call, outcome) in enumerate(zip(calls, history)):
        command = str(outcome.get("command", ""))
        if command != call["command"]:
            raise ValueError(f"tool call and command history differ at index {index}")
        exit_code = outcome.get("exit_code")
        if isinstance(exit_code, bool) or not isinstance(exit_code, int):
            raise ValueError(f"invalid command exit code at index {index}")
        normalized = _normalized_command(command)
        output = outputs.get(call["tool_call_id"], "")
        output_fingerprint = _sha_text(_normalized_output(output))
        prior = prior_by_command[normalized]
        prior_failures = [item for item in prior if item["exit_code"] != 0]
        same_signature_failures = [
            item
            for item in prior_failures
            if item["output_sha256"] == output_fingerprint
        ]
        decision = {
            "index": index,
            "tool_call_id": call["tool_call_id"],
            "command": command,
            "command_sha256": _sha_text(normalized),
            "reason": call["reason"],
            "action_class": _action_class(command),
            "exit_code": exit_code,
            "output_sha256": output_fingerprint,
            "output_chars": len(output),
            "exact_prior_attempts": len(prior),
            "exact_prior_failures": len(prior_failures),
            "same_output_prior_failures": len(same_signature_failures),
            "recovered_exact_failure": exit_code == 0 and bool(prior_failures),
        }
        decisions.append(decision)
        prior.append(decision)

    failed = [item for item in decisions if item["exit_code"] != 0]
    repeated_after_failure = [item for item in decisions if item["exact_prior_failures"]]
    same_output_repeats = [item for item in repeated_after_failure if item["same_output_prior_failures"]]
    recovered = [item for item in decisions if item["recovered_exact_failure"]]
    return {
        "commands": len(decisions),
        "failed_commands": len(failed),
        "mutation_commands": sum(item["action_class"] == "mutation" for item in decisions),
        "observation_commands": sum(item["action_class"] == "observation" for item in decisions),
        "unsupported_commands": sum(item["action_class"] == "unsupported" for item in decisions),
        "exact_retries_after_failure": len(repeated_after_failure),
        "same_output_retries_after_failure": len(same_output_repeats),
        "exact_failure_recoveries": len(recovered),
        "decisions": decisions,
    }


def analyze_trajectory_file(path: Path) -> dict[str, Any]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if not all(isinstance(item, dict) for item in records):
        raise ValueError("trajectory records must be objects")
    result = analyze_trajectory_records(records)
    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        **result,
    }


def aggregate_trajectory_analyses(cases: list[dict[str, Any]]) -> dict[str, Any]:
    totals = Counter()
    fields = (
        "commands",
        "failed_commands",
        "mutation_commands",
        "observation_commands",
        "unsupported_commands",
        "exact_retries_after_failure",
        "same_output_retries_after_failure",
        "exact_failure_recoveries",
    )
    for case in cases:
        for field in fields:
            totals[field] += int(case[field])
    return {"cases": len(cases), **{field: totals[field] for field in fields}}
