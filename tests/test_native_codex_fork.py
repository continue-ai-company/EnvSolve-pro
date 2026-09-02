from __future__ import annotations

from pathlib import Path

import pytest

from envsolve_harness.runners.native_codex_fork import (
    CompletedCodexPrefix,
    build_tool_free_native_fork,
    fork_pair_has_same_completed_prefix,
)


def _completed_prefix() -> CompletedCodexPrefix:
    return CompletedCodexPrefix.from_events(
        [
            {"type": "thread.started", "thread_id": "parent-session"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message"}},
            {"type": "turn.completed", "usage": {"input_tokens": 10}},
        ],
        '{"bootstrap_script":"true","summary":"done"}',
    )


def _plan(branch: str, parent: CompletedCodexPrefix):
    return build_tool_free_native_fork(
        branch=branch,
        parent=parent,
        codex_executable=Path("/Applications/ChatGPT.app/codex"),
        model="gpt-5.6",
        schema_path=Path("schema.json"),
        events_path=Path(f"{branch}.jsonl"),
        output_path=Path(f"{branch}.json"),
        prompt=f"{branch} payload",
    )


def test_f_and_n_use_the_same_completed_parent_and_native_fork() -> None:
    parent = _completed_prefix()
    feedback = _plan("F", parent)
    null = _plan("N", parent)

    assert fork_pair_has_same_completed_prefix(feedback, null)
    assert feedback.command[:3] == (
        "/Applications/ChatGPT.app/codex",
        "exec",
        "fork",
    )
    assert feedback.command[-2:] == ("parent-session", "-")
    assert null.command[-2:] == ("parent-session", "-")
    assert "--ephemeral" not in feedback.command
    assert feedback.parent.final_output == null.parent.final_output


def test_both_forks_disable_shell_apps_and_parent_mcp() -> None:
    parent = _completed_prefix()
    for plan in (_plan("F", parent), _plan("N", parent)):
        rendered = "\n".join(plan.command)
        assert 'features.shell_tool=false' in rendered
        assert 'features.apps=false' in rendered
        assert 'features.multi_agent=false' in rendered
        assert 'mcp_servers.envsolve_container.enabled=false' in rendered


def test_incomplete_parent_is_rejected() -> None:
    with pytest.raises(ValueError, match="completed Codex turn"):
        CompletedCodexPrefix.from_events(
            [
                {"type": "thread.started", "thread_id": "parent-session"},
                {"type": "turn.started"},
            ],
            "non-empty",
        )

