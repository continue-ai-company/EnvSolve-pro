from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from statistics import median
from typing import Any


ISSUE_COUNT = re.compile(r'"issues_count"\s*:\s*(\d+)')
TOTAL_COUNT = re.compile(r"\btotal\s*:\s*(\d+)\b", re.IGNORECASE)
LINE_COUNT = re.compile(r"^\s*count\s*[:=]?\s*(\d+)\s*$", re.IGNORECASE | re.MULTILINE)
MISSING_COUNT = re.compile(
    r"\b(?:total\s+)?missing\s*imports?(?:\s*\([^)]*\))?\s*[:=]?\s*(\d+)\b",
    re.IGNORECASE,
)
REPORT_MISSING_COUNT = re.compile(
    r"\breportMissingImports(?:\s+count)?\s*[:=]?\s*(\d+)\b",
    re.IGNORECASE,
)
PYRIGHT_EXECUTION = re.compile(
    r"(?:python\S*\s+-m\s+pyright\b|npx\s+pyright\b|"
    r"(?:^|[;&|]\s*|timeout\s+\d+\s+)(?:/\S+/)?pyright\s)",
    re.IGNORECASE,
)
EXPLICIT_PARTIAL_PYRIGHT_SCOPE = re.compile(
    r"(?:python\S*\s+-m\s+pyright|(?:^|[;&|]\s*|timeout\s+\d+\s+)"
    r"(?:/\S+/)?pyright)\s+(?:src|tests|examples|capi|doc)(?:\s|$)",
    re.IGNORECASE,
)
PACKAGE_OPERATION = re.compile(
    r"(?:^|[;&|]\s*|\s)(?:python\S*\s+-m\s+)?pip\s+(?:install|uninstall)|"
    r"(?:^|[;&|]\s*|\s)(?:uv\s+pip|conda|mamba|apt(?:-get)?)\s+install",
    re.IGNORECASE,
)
ENVIRONMENT_OPERATION = re.compile(
    r"(?:python\S*\s+-m\s+venv|virtualenv|pyenv\s+(?:install|local|shell)|"
    r"conda\s+create|source\s+\S*(?:activate|bin/activate)|VIRTUAL_ENV=|PATH=)",
    re.IGNORECASE,
)
RUNTIME_PROBE = re.compile(
    r"(?:pytest|pyright|mypy|python\S*\s+(?:-c|-m\s+(?:pytest|compileall))|"
    r"importlib\.import_module)",
    re.IGNORECASE,
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if isinstance(value, dict):
            records.append(value)
    return records


def _normalize_command(command: str) -> str:
    return " ".join(command.split())


def _goal_issue_count(command: str, output: object) -> int | None:
    if not isinstance(output, str):
        return None
    matches = ISSUE_COUNT.findall(output)
    if matches:
        return int(matches[-1])
    if "reportMissingImports" not in command or not PYRIGHT_EXECUTION.search(command):
        return None
    if EXPLICIT_PARTIAL_PYRIGHT_SCOPE.search(command):
        return None
    for pattern in (TOTAL_COUNT, LINE_COUNT, MISSING_COUNT, REPORT_MISSING_COUNT):
        matches = pattern.findall(output)
        if matches:
            return int(matches[-1])
    diagnostic_lines = [
        line
        for line in output.splitlines()
        if "could not be resolved" in line or "reportMissingImports" in line
    ]
    if diagnostic_lines:
        return len(diagnostic_lines)
    filtered_output = any(
        marker in command
        for marker in ("if x.get('rule')", 'if x.get("rule")', "grep")
    )
    parse_failed = any(
        marker in output
        for marker in ("Traceback", "JSONDecodeError", "command not found")
    )
    has_summary_evidence = "summary" in output or "filesAnalyzed" in output
    if filtered_output and has_summary_evidence and not parse_failed:
        return 0
    return None


def analyze_trajectory(path: Path, run_id: str | None = None) -> dict[str, Any]:
    events = _read_jsonl(path)
    shell_actions: list[dict[str, Any]] = []
    candidate_events: list[tuple[int, str]] = []
    certification_events: list[tuple[int, str]] = []
    for event in events:
        if event.get("event") == "tool_result":
            result = event.get("result")
            request_index = event.get("request_index")
            if isinstance(result, dict) and isinstance(request_index, int):
                tool_name = event.get("tool_name")
                if tool_name == "submit_and_replay":
                    candidate_events.append((request_index, "submit-and-replay"))
                    if result.get("status") == "pass":
                        certification_events.append(
                            (request_index, "clean-replay-pass")
                        )
                elif tool_name == "submit_bootstrap":
                    candidate_events.append((request_index, "submit-bootstrap"))
                    if result.get("accepted") is True:
                        certification_events.append(
                            (request_index, "accepted-submission")
                        )
        if event.get("event") != "tool_result" or event.get("tool_name") != "envbench_shell":
            continue
        result = event.get("result")
        if not isinstance(result, dict):
            continue
        command = str(result.get("command", ""))
        shell_actions.append(
            {
                "request_index": event.get("request_index"),
                "command": command,
                "normalized_command": _normalize_command(command),
                "exit_code": result.get("exit_code"),
                "timed_out": bool(result.get("timed_out")),
                "infrastructure_error": result.get("infrastructure_error"),
                "goal_issue_count": _goal_issue_count(command, result.get("output")),
            }
        )

    first_satisfying_position = next(
        (
            position
            for position, action in enumerate(shell_actions)
            if action["goal_issue_count"] == 0
        ),
        None,
    )
    first_satisfying_request = (
        shell_actions[first_satisfying_position]["request_index"]
        if first_satisfying_position is not None
        else None
    )
    first_candidate = min(candidate_events, default=None)
    first_certification = min(certification_events, default=None)
    prefix = [
        action
        for action in shell_actions
        if first_candidate is None
        or not isinstance(action["request_index"], int)
        or action["request_index"] <= first_candidate[0]
    ]
    goal_checks = [item for item in prefix if item["goal_issue_count"] is not None]
    issue_counts = [int(item["goal_issue_count"]) for item in goal_checks]

    best: int | None = None
    previous: int | None = None
    transitions = Counter()
    best_progression: list[int] = []
    for count in issue_counts:
        if previous is not None:
            if count < previous:
                transitions["improving"] += 1
            elif count > previous:
                transitions["regressing"] += 1
            else:
                transitions["stagnant"] += 1
        if best is None or count < best:
            best = count
            transitions["new_best"] += 1
        best_progression.append(best)
        previous = count

    check_positions = [prefix.index(item) + 1 for item in goal_checks]
    check_gaps = [
        current - previous_position
        for previous_position, current in zip([0, *check_positions[:-1]], check_positions)
    ]
    normalized_commands = [
        item["normalized_command"]
        for item in prefix
        if item["goal_issue_count"] is None
    ]
    command_counts = Counter(normalized_commands)
    repeated_command_executions = sum(count - 1 for count in command_counts.values())

    def count_matching(pattern: re.Pattern[str]) -> int:
        return sum(bool(pattern.search(item["command"])) for item in prefix)

    return {
        "run_id": run_id,
        "trajectory": str(path),
        "shell_actions_total": len(shell_actions),
        "first_satisfying_request": first_satisfying_request,
        "first_satisfying_shell_action": (
            first_satisfying_position + 1 if first_satisfying_position is not None else None
        ),
        "first_candidate_request": first_candidate[0] if first_candidate else None,
        "first_candidate_source": first_candidate[1] if first_candidate else None,
        "first_certification_request": (
            first_certification[0] if first_certification else None
        ),
        "first_certification_source": (
            first_certification[1] if first_certification else None
        ),
        "goal_to_candidate_request_delta": (
            first_candidate[0] - first_satisfying_request
            if first_candidate is not None
            and isinstance(first_satisfying_request, int)
            else None
        ),
        "goal_satisfied_without_candidate": (
            isinstance(first_satisfying_request, int) and first_candidate is None
        ),
        "pre_candidate": {
            "shell_actions": len(prefix),
            "failed_shell_actions": sum(
                item["exit_code"] not in (0, None) for item in prefix
            ),
            "timed_out_shell_actions": sum(item["timed_out"] for item in prefix),
            "infrastructure_error_actions": sum(
                item["infrastructure_error"] is not None for item in prefix
            ),
            "exact_repeated_non_goal_command_executions": repeated_command_executions,
            "package_operations": count_matching(PACKAGE_OPERATION),
            "environment_operations": count_matching(ENVIRONMENT_OPERATION),
            "runtime_or_test_probes": count_matching(RUNTIME_PROBE),
            "goal_checks": len(goal_checks),
            "goal_issue_counts": issue_counts,
            "goal_best_progression": best_progression,
            "goal_transitions": dict(sorted(transitions.items())),
            "shell_actions_per_goal_check": (
                len(prefix) / len(goal_checks) if goal_checks else None
            ),
            "median_shell_gap_between_goal_checks": (
                median(check_gaps) if check_gaps else None
            ),
            "maximum_shell_gap_between_goal_checks": max(check_gaps, default=None),
        },
    }


def _find_trajectory(runs_root: Path, run_id: str) -> Path:
    matches = sorted((runs_root / run_id).glob("*/generation/trajectory.jsonl"))
    if len(matches) != 1:
        raise ValueError(f"Expected one trajectory for {run_id}, found {len(matches)}")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--run-id", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    episodes = [
        analyze_trajectory(_find_trajectory(args.runs_root, run_id), run_id)
        for run_id in args.run_id
    ]
    pre = [episode["pre_candidate"] for episode in episodes]
    result = {
        "schema": "envsolve-pro-v2-pre-candidate-trajectory-analysis-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim_scope": "Consumed-development trajectory diagnosis only.",
        "episode_count": len(episodes),
        "episodes_reaching_satisfying_state": sum(
            episode["first_satisfying_request"] is not None for episode in episodes
        ),
        "episodes_reaching_candidate_boundary": sum(
            episode["first_candidate_request"] is not None for episode in episodes
        ),
        "episodes_reaching_certification_boundary": sum(
            episode["first_certification_request"] is not None
            for episode in episodes
        ),
        "episodes_satisfying_goal_without_candidate": sum(
            episode["goal_satisfied_without_candidate"] for episode in episodes
        ),
        "aggregate": {
            "pre_candidate_shell_actions": sum(item["shell_actions"] for item in pre),
            "failed_shell_actions": sum(item["failed_shell_actions"] for item in pre),
            "exact_repeated_non_goal_command_executions": sum(
                item["exact_repeated_non_goal_command_executions"] for item in pre
            ),
            "package_operations": sum(item["package_operations"] for item in pre),
            "environment_operations": sum(item["environment_operations"] for item in pre),
            "runtime_or_test_probes": sum(item["runtime_or_test_probes"] for item in pre),
            "goal_checks": sum(item["goal_checks"] for item in pre),
            "improving_goal_transitions": sum(
                item["goal_transitions"].get("improving", 0) for item in pre
            ),
            "stagnant_goal_transitions": sum(
                item["goal_transitions"].get("stagnant", 0) for item in pre
            ),
            "regressing_goal_transitions": sum(
                item["goal_transitions"].get("regressing", 0) for item in pre
            ),
        },
        "episodes": episodes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
