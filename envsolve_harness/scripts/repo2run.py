from __future__ import annotations

from dataclasses import dataclass
import re
import shlex
from typing import Any

from envsolve_harness.scripts.replay_actions import ReplayAction, analyze_successful_command
from envsolve_harness.scripts.open_program import OPEN_PROGRAM_POLICY

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

INTERNAL_TOOL_PATHS = (
    "/home/tools/runtest.py",
    "/home/tools/poetryruntest.py",
    "/home/tools/runpipreqs.py",
    "/home/tools/generate_diff.py",
)

_REPO_PATH = re.compile(
    r"(?<![A-Za-z0-9_./-])/repo(?=$|[/\s;&|<>()\"'])"
)


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
    return _REPO_PATH.sub('"${PROJECT_ROOT}"', value)


def _map_repo_path_open(value: str) -> str:
    return _REPO_PATH.sub("${PROJECT_ROOT}", value)


def _portable_pip_download(command: str) -> str | None:
    """Translate Repo2Run's private download helper into its pip effect."""

    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    prefix = ["python", "/home/tools/pip_download.py", "-p"]
    if parts[:3] != prefix or len(parts) not in {4, 6}:
        return None
    name_match = re.match(
        r"[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[A-Za-z0-9_,.-]+\])?",
        parts[3],
    )
    if name_match is None:
        return None
    package = name_match.group(0)
    specifier = parts[3][len(package) :]
    if len(parts) == 6:
        if specifier or parts[4] != "-v":
            return None
        specifier = parts[5]
    if specifier and not re.fullmatch(
        r"[A-Za-z0-9*+!._,<>=~ -]+",
        specifier,
    ):
        return None
    return f"python -m pip install {shlex.quote(package + specifier)}"


def compile_repo2run_open_program(
    records: list[dict[str, Any]],
) -> DistillationResult:
    """Compile Repo2Run sandbox effects while preserving successful shell syntax."""

    replay: list[str] = ['PROJECT_ROOT="$(pwd)"', *_python_switch("3.10")]
    kept: list[str] = []
    dropped: list[str] = []
    unsupported: list[str] = []
    actions: list[ReplayAction] = [
        ReplayAction(
            "runtime_configure",
            "\n".join(_python_switch("3.10")),
            "ambient-runtime:python:3.10",
        )
    ]
    poetry_environment_created = False
    for record in records:
        command = str(record.get("command", "")).strip()
        if not command:
            continue
        if "\x00" in command:
            unsupported.append(f"NUL byte under {OPEN_PROGRAM_POLICY}")
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
            switch = _python_switch(parts[1])
            replay = ['PROJECT_ROOT="$(pwd)"', *switch]
            kept = [command]
            actions = [ReplayAction("runtime_configure", "\n".join(switch), command)]
            poetry_environment_created = False
            continue
        if command == "clear_configuration":
            switch = _python_switch("3.10")
            replay = ['PROJECT_ROOT="$(pwd)"', *switch]
            kept = [command]
            actions = [ReplayAction("runtime_configure", "\n".join(switch), command)]
            poetry_environment_created = False
            continue
        if action == "change_base_image":
            unsupported.append(command)
            continue
        if command in INTERNAL_COMMANDS or action == "pipdeptree":
            dropped.append(command)
            continue

        if command.startswith("python /home/tools/pip_download.py"):
            mapped_download = _portable_pip_download(command)
            if mapped_download is None:
                unsupported.append(command)
                continue
            replay.append(mapped_download)
            kept.append(command)
            actions.append(
                ReplayAction("python_package_install", mapped_download, command)
            )
            continue

        if any(path in command for path in INTERNAL_TOOL_PATHS):
            dropped.append(command)
            continue
        if "/home/tools/" in command:
            unsupported.append(f"private-tool-path: {command}")
            continue

        mapped = _map_repo_path_open(command)
        working_dir = str(record.get("dir", "/"))
        if working_dir.startswith("/repo/"):
            relative_dir = working_dir[len("/repo/") :]
            if ".." in relative_dir.split("/"):
                unsupported.append(f"cwd={working_dir}: {command}")
                continue
            mapped = f'cd "${{PROJECT_ROOT}}/{relative_dir}" && {mapped}'
        elif working_dir not in {"/", "/repo"}:
            unsupported.append(f"cwd={working_dir}: {command}")
            continue
        analysis = analyze_successful_command(mapped)
        if analysis.dropped and analysis.unsupported_reason is None:
            dropped.append(command)
            continue
        replay.append(mapped)
        kept.append(command)
        if re.search(r"(?:^|&&)\s*poetry\s+install(?:\s|$)", mapped):
            poetry_environment_created = True

    if poetry_environment_created:
        activation = 'source "$(poetry env info --path)/bin/activate"'
        replay.append(activation)
        actions.append(
            ReplayAction(
                "environment_activate",
                activation,
                "native-verifier-context:poetry-run",
            )
        )

    return DistillationResult(
        script="\n".join(replay) + "\n",
        kept_commands=tuple(kept),
        dropped_commands=tuple(dropped),
        unsupported_commands=tuple(unsupported),
        actions=tuple(actions),
    )


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
