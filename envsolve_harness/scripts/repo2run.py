from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from envsolve_harness.scripts.replay_actions import ReplayAction, analyze_successful_command

OBSERVATION_COMMANDS = {
    "cd", "ls", "cat", "pwd", "whoami", "date", "df", "du", "free", "uname",
    "uptime", "ps", "pgrep", "top", "vmstat", "tail", "head", "more", "less",
    "grep", "find", "locate", "whereis", "which", "file", "stat", "cmp", "diff",
    "md5sum", "sha256sum", "sort", "uniq", "wc", "tr", "cut", "awk", "env",
    "printenv", "lscpu", "lsusb", "lspci", "pipdeptree",
}

INTERNAL_COMMANDS = {
    "python /home/tools/runtest.py",
    "python /home/tools/poetryruntest.py",
    "python /home/tools/runpipreqs.py",
    "python /home/tools/generate_diff.py",
    "$pwd$",
    "$pip list --format json$",
}


@dataclass(frozen=True)
class DistillationResult:
    script: str
    kept_commands: tuple[str, ...]
    dropped_commands: tuple[str, ...]
    unsupported_commands: tuple[str, ...]
    actions: tuple[ReplayAction, ...]


def _python_switch(version: str) -> list[str]:
    escaped = re.escape(version)
    return [
        'export PATH="${PYENV_ROOT}/shims:${PYENV_ROOT}/bin:${PATH}"',
        f'PYTHON_VERSION="$(pyenv versions --bare | grep -E "^{escaped}(\\.|$)" | sort -V | tail -n1)"',
        'test -n "$PYTHON_VERSION"',
        'pyenv global "$PYTHON_VERSION"',
        "hash -r",
    ]


def _map_repo_path(value: str) -> str:
    return value.replace("/repo", '"${PROJECT_ROOT}"')


def distill_repo2run_commands(records: list[dict[str, Any]]) -> DistillationResult:
    replay: list[str] = ['PROJECT_ROOT="$(pwd)"']
    kept: list[str] = []
    dropped: list[str] = []
    unsupported: list[str] = []
    actions: list[ReplayAction] = []

    for record in records:
        command = str(record.get("command", "")).strip()
        if not command:
            continue
        if str(record.get("returncode")) != "0":
            dropped.append(command)
            continue
        action = command.split(maxsplit=1)[0]

        if action == "change_python_version":
            parts = command.split()
            if len(parts) != 2 or not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", parts[1]):
                unsupported.append(command)
                continue
            replay = ['PROJECT_ROOT="$(pwd)"', *_python_switch(parts[1])]
            kept = [command]
            actions = [
                ReplayAction(
                    "runtime_configure",
                    "\n".join(_python_switch(parts[1])),
                    command,
                )
            ]
            continue
        if command == "clear_configuration":
            replay = ['PROJECT_ROOT="$(pwd)"', *_python_switch("3.10")]
            kept = [command]
            actions = [
                ReplayAction(
                    "runtime_configure",
                    "\n".join(_python_switch("3.10")),
                    command,
                )
            ]
            continue
        if action == "change_base_image":
            unsupported.append(command)
            continue
        if command in INTERNAL_COMMANDS or action == "pipdeptree":
            dropped.append(command)
            continue

        mapped = _map_repo_path(command)
        working_dir = str(record.get("dir", "/"))
        if working_dir.startswith("/repo/"):
            relative_dir = working_dir[len("/repo/") :]
            mapped = f'cd "${{PROJECT_ROOT}}/{relative_dir}" && {mapped}'
        elif working_dir not in {"/", "/repo"}:
            unsupported.append(f"cwd={working_dir}: {command}")
            continue
        analysis = analyze_successful_command(mapped)
        if analysis.unsupported_reason:
            unsupported.append(f"{analysis.unsupported_reason}: {command}")
            continue
        if analysis.dropped:
            dropped.append(command)
            continue
        replay.extend(item.command for item in analysis.actions)
        actions.extend(analysis.actions)
        kept.append(command)

    return DistillationResult(
        script="\n".join(replay) + "\n",
        kept_commands=tuple(kept),
        dropped_commands=tuple(dropped),
        unsupported_commands=tuple(unsupported),
        actions=tuple(actions),
    )
