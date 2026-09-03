from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


def _toml(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


@dataclass(frozen=True)
class CompletedCodexPrefix:
    session_id: str
    event_count: int
    completed_turn_count: int
    final_output: str

    @classmethod
    def from_events(
        cls,
        records: list[dict[str, Any]],
        final_output: str,
    ) -> "CompletedCodexPrefix":
        started = [
            item.get("thread_id")
            for item in records
            if item.get("type") == "thread.started"
            and isinstance(item.get("thread_id"), str)
        ]
        if len(started) != 1:
            raise ValueError("P0 must contain exactly one Codex thread.started event")
        completed = sum(item.get("type") == "turn.completed" for item in records)
        if completed < 1 or not records or records[-1].get("type") != "turn.completed":
            raise ValueError("P0 must end with a completed Codex turn")
        if not final_output.strip():
            raise ValueError("P0 final output must be non-empty")
        return cls(
            session_id=str(started[0]),
            event_count=len(records),
            completed_turn_count=completed,
            final_output=final_output,
        )


@dataclass(frozen=True)
class NativeCodexForkPlan:
    branch: str
    parent: CompletedCodexPrefix
    command: tuple[str, ...]
    prompt: str
    events_path: Path
    output_path: Path


def build_tool_free_native_fork(
    *,
    branch: str,
    parent: CompletedCodexPrefix,
    codex_executable: Path,
    model: str,
    reasoning_effort: str,
    schema_path: Path,
    events_path: Path,
    output_path: Path,
    prompt: str,
) -> NativeCodexForkPlan:
    if branch not in {"F", "N"}:
        raise ValueError("Native fork branch must be F or N")
    if not prompt.strip():
        raise ValueError("Native fork prompt must be non-empty")
    overrides = {
        "approval_policy": "never",
        "project_doc_max_bytes": 0,
        "web_search": "disabled",
        "features.shell_tool": False,
        "features.apps": False,
        "features.goals": False,
        "features.hooks": False,
        "features.memories": False,
        "features.multi_agent": False,
        "features.remote_plugin": False,
        "mcp_servers.envsolve_container.enabled": False,
        "model_reasoning_effort": reasoning_effort,
    }
    command = [
        str(codex_executable),
        "exec",
        "fork",
        "--json",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--model",
        model,
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(output_path),
    ]
    for name, value in overrides.items():
        command.extend(["--config", f"{name}={_toml(value)}"])
    command.extend([parent.session_id, "-"])
    return NativeCodexForkPlan(
        branch=branch,
        parent=parent,
        command=tuple(command),
        prompt=prompt,
        events_path=events_path,
        output_path=output_path,
    )


def fork_pair_has_same_completed_prefix(
    first: NativeCodexForkPlan,
    second: NativeCodexForkPlan,
) -> bool:
    return bool(
        {first.branch, second.branch} == {"F", "N"}
        and first.parent == second.parent
        and first.command[-2] == second.command[-2] == first.parent.session_id
        and first.parent.completed_turn_count >= 1
    )
