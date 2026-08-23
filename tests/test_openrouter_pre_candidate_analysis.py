from __future__ import annotations

import json
from pathlib import Path
import tempfile

from experiments.analyze_openrouter_pre_candidate import (
    _goal_issue_count,
    analyze_trajectory,
)


def _event(request: int, command: str, output: str, exit_code: int = 0) -> str:
    return json.dumps(
        {
            "event": "tool_result",
            "request_index": request,
            "tool_name": "envbench_shell",
            "result": {
                "command": command,
                "output": output,
                "exit_code": exit_code,
                "timed_out": False,
                "infrastructure_error": None,
            },
        }
    )


def _replay_event(request: int, status: str) -> str:
    return json.dumps(
        {
            "event": "tool_result",
            "request_index": request,
            "tool_name": "submit_and_replay",
            "result": {"status": status},
        }
    )


def test_goal_satisfaction_does_not_imply_candidate_formation() -> None:
    records = [
        _event(1, "ls", "files"),
        _event(2, "python -m venv .venv", ""),
        _event(3, "goal", '{"issues_count": 10}'),
        _event(4, "pip install alpha", "installed"),
        _event(5, "goal", '{"issues_count": 5}'),
        _event(6, "pip install alpha", "already installed"),
        _event(7, "goal", '{"issues_count": 5}'),
        _event(8, "python -c 'import alpha'", "failed", exit_code=1),
        _event(9, "goal", '{"issues_count": 7}'),
        _event(10, "pip install beta", "installed"),
        _event(11, "goal", '{"issues_count": 0}'),
        _event(12, "pytest", "passed"),
    ]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "trajectory.jsonl"
        path.write_text("\n".join(records) + "\n", encoding="utf-8")
        result = analyze_trajectory(path, "run-1")

    pre = result["pre_candidate"]
    assert result["first_satisfying_request"] == 11
    assert result["first_candidate_request"] is None
    assert result["first_candidate_source"] is None
    assert result["first_certification_request"] is None
    assert result["goal_satisfied_without_candidate"] is True
    assert result["first_satisfying_shell_action"] == 11
    assert result["shell_actions_total"] == 12
    assert pre["shell_actions"] == 12
    assert pre["goal_issue_counts"] == [10, 5, 5, 7, 0]
    assert pre["goal_best_progression"] == [10, 5, 5, 5, 0]
    assert pre["goal_transitions"] == {
        "improving": 2,
        "new_best": 3,
        "regressing": 1,
        "stagnant": 1,
    }
    assert pre["failed_shell_actions"] == 1
    assert pre["exact_repeated_non_goal_command_executions"] == 1
    assert pre["package_operations"] == 3
    assert pre["environment_operations"] == 1
    assert pre["runtime_or_test_probes"] == 2


def test_pre_candidate_analysis_retains_full_failed_episode() -> None:
    records = [
        _event(1, "goal", '{"issues_count": 4}'),
        _event(2, "pip install alpha", "failed", exit_code=1),
        _event(3, "goal", '{"issues_count": 4}'),
    ]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "trajectory.jsonl"
        path.write_text("\n".join(records) + "\n", encoding="utf-8")
        result = analyze_trajectory(path)

    assert result["first_satisfying_request"] is None
    assert result["pre_candidate"]["shell_actions"] == 3
    assert result["pre_candidate"]["goal_transitions"]["stagnant"] == 1


def test_goal_count_parses_agent_equivalent_pyright_summaries() -> None:
    command = (
        "python -m pyright --outputjson | python -c \""
        "[print(x) for x in d.get('generalDiagnostics', []) "
        "if x.get('rule') == 'reportMissingImports']\""
    )
    assert _goal_issue_count(command, "count 2\n") == 2
    assert _goal_issue_count(command, "N unique: 0 total: 0\n") == 0
    assert _goal_issue_count(command, "summary {'errorCount': 48}\n") == 0
    assert _goal_issue_count(command, "total diag 1057 missingImports 438\n") == 438
    assert _goal_issue_count(command, "missing imports: 748\n") == 748
    assert _goal_issue_count(command, "total missing imports (full): 0\n") == 0
    assert _goal_issue_count(command, "reportMissingImports count: 0\n") == 0
    assert (
        _goal_issue_count(
            "python -m pyright src tests --outputjson | python -c "
            "\"[print(x) for x in d if x.get('rule') == "
            "'reportMissingImports']\"",
            "total missing imports: 0\n",
        )
        is None
    )
    assert _goal_issue_count("pytest", "summary {'errorCount': 0}\n") is None
    assert (
        _goal_issue_count(
            "grep -r 'reportMissingImports|pyright' pyproject.toml",
            "pyproject.toml: pyright config\n",
        )
        is None
    )


def test_clean_replay_pass_bounds_pre_candidate_actions_without_shell_zero() -> None:
    records = [
        _event(1, "goal", '{"issues_count": 4}'),
        _event(2, "pip install alpha", "installed"),
        _replay_event(3, "pass"),
        _event(4, "pytest", "passed"),
    ]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "trajectory.jsonl"
        path.write_text("\n".join(records) + "\n", encoding="utf-8")
        result = analyze_trajectory(path)

    assert result["first_satisfying_request"] is None
    assert result["first_candidate_request"] == 3
    assert result["first_candidate_source"] == "submit-and-replay"
    assert result["first_certification_request"] == 3
    assert result["first_certification_source"] == "clean-replay-pass"
    assert result["pre_candidate"]["shell_actions"] == 2


def test_goal_to_candidate_delay_is_measured_separately() -> None:
    records = [
        _event(1, "goal", '{"issues_count": 0}'),
        _event(2, "pytest", "passed"),
        _replay_event(4, "fail"),
    ]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "trajectory.jsonl"
        path.write_text("\n".join(records) + "\n", encoding="utf-8")
        result = analyze_trajectory(path)

    assert result["first_satisfying_request"] == 1
    assert result["first_candidate_request"] == 4
    assert result["first_certification_request"] is None
    assert result["goal_to_candidate_request_delta"] == 3
    assert result["goal_satisfied_without_candidate"] is False
    assert result["pre_candidate"]["shell_actions"] == 2
