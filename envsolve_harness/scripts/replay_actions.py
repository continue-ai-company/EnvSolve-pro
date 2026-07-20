from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from enum import Enum
import re
import shlex
from typing import Any


REPLAY_IR_POLICY = "typed-replay-ir-v8"


class ReplayActionKind(str, Enum):
    VIRTUAL_ENVIRONMENT_CREATE = "virtual_environment_create"
    PYTHON_PACKAGE_INSTALL = "python_package_install"
    SYSTEM_PACKAGE_INSTALL = "system_package_install"
    PACKAGE_INDEX_UPDATE = "package_index_update"
    RUNTIME_CONFIGURE = "runtime_configure"
    ENVIRONMENT_EXPORT = "environment_export"
    ENVIRONMENT_ACTIVATE = "environment_activate"


@dataclass(frozen=True)
class ReplayAction:
    kind: str
    command: str
    source_command: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CommandAnalysis:
    actions: tuple[ReplayAction, ...] = ()
    dropped: bool = False
    unsupported_reason: str | None = None
    project_path_mapped: bool = False


OBSERVATION_EXECUTABLES = {
    "cat", "cmp", "cut", "date", "df", "diff", "du", "env", "file",
    "find", "free", "grep", "head", "less", "locate", "ls", "lscpu", "lspci",
    "lsusb", "md5sum", "more", "pgrep", "pipdeptree", "printenv", "ps", "pwd",
    "sha256sum", "sort", "stat", "tail", "top", "tr", "uname", "uniq", "uptime",
    "vmstat", "wc", "whereis", "which", "whoami",
}

_VENV_EXECUTABLE_PREFIX = r"(?:(?:\$\{PROJECT_ROOT\}/)?(?:\.venv|venv)/bin/)?"
PYTHON_PATTERN = re.compile(rf"^{_VENV_EXECUTABLE_PREFIX}python\d*(?:\.\d+)?$")
PIP_PATTERN = re.compile(rf"^{_VENV_EXECUTABLE_PREFIX}pip\d*(?:\.\d+)?$")
LOG_FILTERS = {"grep", "head", "tail"}
OBSERVATION_PIPE_FILTERS = {"cut", "grep", "head", "sort", "tail", "uniq", "wc"}
FIND_MUTATION_OPTIONS = {
    "-delete",
    "-exec",
    "-execdir",
    "-fls",
    "-fprint",
    "-fprint0",
    "-fprintf",
    "-ok",
    "-okdir",
}
SHELL_STARTUP_FILES = {
    "~/.bash_profile",
    "~/.bashrc",
    "~/.profile",
    "$HOME/.bash_profile",
    "$HOME/.bashrc",
    "$HOME/.profile",
    "${HOME}/.bash_profile",
    "${HOME}/.bashrc",
    "${HOME}/.profile",
}
SHELL_SUBSTITUTION_MARKERS = ("$(", "`", "<(", ">(")
DANGEROUS_ENVIRONMENT_VARIABLES = {
    "DYLD_INSERT_LIBRARIES",
    "DYLD_LIBRARY_PATH",
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "MYPYPATH",
    "PYTHONHOME",
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "PYTHONUSERBASE",
}


def _split_top_level(value: str, delimiter: str) -> list[str] | None:
    parts: list[str] = []
    start = 0
    quote: str | None = None
    escaped = False
    substitution_depth = 0
    index = 0
    while index < len(value):
        char = value[index]
        if escaped:
            escaped = False
            index += 1
            continue
        if char == "\\" and quote != "'":
            escaped = True
            index += 1
            continue
        if quote:
            if char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
            index += 1
            continue
        if value.startswith("$(", index):
            substitution_depth += 1
            index += 2
            continue
        if char == ")" and substitution_depth:
            substitution_depth -= 1
            index += 1
            continue
        if substitution_depth == 0 and value.startswith(delimiter, index):
            parts.append(value[start:index].strip())
            index += len(delimiter)
            start = index
            continue
        index += 1
    if quote or substitution_depth or escaped:
        return None
    parts.append(value[start:].strip())
    return parts


def _tokens(command: str) -> list[str] | None:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return None


def _punctuated_tokens(command: str) -> list[str] | None:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="|&;<>")
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return None


def _without_sudo(tokens: list[str]) -> list[str]:
    return tokens[1:] if tokens and tokens[0] == "sudo" else tokens


def _valid_environment_export(tokens: list[str]) -> bool:
    if len(tokens) < 2:
        return False
    for assignment in tokens[1:]:
        if "=" not in assignment:
            return False
        name, value = assignment.split("=", 1)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            return False
        if name in DANGEROUS_ENVIRONMENT_VARIABLES or name.startswith("PYRIGHT_"):
            return False
        if any(marker in value for marker in SHELL_SUBSTITUTION_MARKERS):
            return False
        if name == "PATH":
            components = value.split(":")
            if any(
                component in {"", "."}
                or any(marker in component for marker in ("$PWD", "${PWD}", "$(pwd)", "${PROJECT_ROOT}"))
                for component in components
            ):
                return False
    return True


def _valid_environment_activation(command: str, tokens: list[str]) -> bool:
    if re.fullmatch(r"(?:source|\.)\s+\$\(poetry env info --path\)/bin/activate", command):
        return True
    if len(tokens) != 2:
        return False
    target = tokens[1]
    return target in {
        ".venv/bin/activate",
        "venv/bin/activate",
        "${PROJECT_ROOT}/.venv/bin/activate",
        "${PROJECT_ROOT}/venv/bin/activate",
    }


def _observation_words(command: str) -> list[str] | None:
    if any(marker in command for marker in SHELL_SUBSTITUTION_MARKERS):
        return None
    tokens = _punctuated_tokens(command)
    if not tokens:
        return None
    words: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in {"|", "||", "&&", ";", "&"}:
            return None
        if token in {"<", ">", ">>", ">&", "&>", "&>>", "<<", "<<<", "<>"}:
            if index + 1 >= len(tokens):
                return None
            target = tokens[index + 1]
            descriptor = words[-1] if words and words[-1] in {"0", "1", "2"} else None
            if descriptor is not None:
                words.pop()
            if token == "<":
                pass
            elif token in {">", ">>", "&>", "&>>"} and target == "/dev/null":
                pass
            elif token == ">&" and target in {"1", "2", "/dev/null"}:
                pass
            else:
                return None
            index += 2
            continue
        if any(character in token for character in "<>"):
            return None
        words.append(token)
        index += 1
    return words or None


def _safe_display_expression(node: ast.AST) -> bool:
    if isinstance(node, (ast.Constant, ast.Name)):
        return True
    if isinstance(node, ast.Attribute):
        return _safe_display_expression(node.value)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_safe_display_expression(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            key is None or _safe_display_expression(key)
            for key in node.keys
        ) and all(_safe_display_expression(value) for value in node.values)
    return False


def _safe_python_probe(source: str) -> bool:
    try:
        module = ast.parse(source)
    except SyntaxError:
        return False
    for statement in module.body:
        if isinstance(statement, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
            continue
        if not (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Name)
            and statement.value.func.id == "print"
            and not statement.value.keywords
            and all(_safe_display_expression(arg) for arg in statement.value.args)
        ):
            return False
    return bool(module.body)


def _is_observation_words(tokens: list[str]) -> bool:
    tokens = _without_sudo(tokens)
    if not tokens:
        return False
    executable = tokens[0].rsplit("/", 1)[-1]
    if executable in {":", "false", "true"}:
        return len(tokens) == 1
    if executable in {"echo", "printf"}:
        return True
    if executable == "find":
        return not any(token in FIND_MUTATION_OPTIONS for token in tokens[1:])
    if executable == "env":
        return all(
            token.startswith("-") or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", token)
            for token in tokens[1:]
        )
    if executable in OBSERVATION_EXECUTABLES:
        return True
    if PIP_PATTERN.fullmatch(executable):
        return len(tokens) > 1 and (
            tokens[1] in {"--version", "-V", "check", "freeze", "index", "list", "show"}
            or (tokens[1] == "install" and "--dry-run" in tokens)
        )
    if PYTHON_PATTERN.fullmatch(executable):
        if len(tokens) > 1 and tokens[1] in {"--version", "-V"}:
            return True
        if len(tokens) > 2 and tokens[1] == "-c":
            return _safe_python_probe(tokens[2])
        return len(tokens) > 2 and tokens[1] == "-m" and tokens[2] in {
            "pytest", "tests", "test", "unittest"
        }
    if executable == "poetry":
        return "--version" in tokens or tokens[1:3] == ["env", "info"]
    if executable == "pyenv":
        return len(tokens) > 1 and tokens[1] in {
            "commands", "prefix", "root", "version", "versions", "which"
        }
    if executable in {"pytest", "tox", "nox"}:
        return True
    if executable == "make" and len(tokens) > 1 and tokens[1] in {
        "check", "lint", "test", "tests"
    }:
        return True
    return any(token in {"--help", "--version"} for token in tokens[1:])


def _is_observation_filter(command: str) -> bool:
    tokens = _observation_words(command)
    if not tokens:
        return False
    executable = tokens[0].rsplit("/", 1)[-1]
    if executable in OBSERVATION_PIPE_FILTERS:
        return True
    if executable != "xargs":
        return False
    remaining = tokens[1:]
    while remaining and remaining[0] in {"-0", "-r", "--no-run-if-empty"}:
        remaining = remaining[1:]
    if not remaining:
        return True
    return _is_observation_words(remaining)


def _is_observation(command: str) -> bool:
    pipeline = _split_top_level(command, "|")
    if pipeline is None or not pipeline:
        return False
    for filter_command in pipeline[1:]:
        if not _is_observation_filter(filter_command):
            return False
    tokens = _observation_words(pipeline[0])
    return bool(tokens and _is_observation_words(tokens))


def _classify_mutation(command: str) -> ReplayActionKind | None:
    tokens = _tokens(command)
    if not tokens:
        return None
    tokens = _without_sudo(tokens)
    if not tokens:
        return None
    executable = tokens[0]
    if (
        PYTHON_PATTERN.fullmatch(executable)
        and len(tokens) == 4
        and tokens[1:3] == ["-m", "venv"]
        and tokens[3] in {".venv", "venv"}
    ):
        return ReplayActionKind.VIRTUAL_ENVIRONMENT_CREATE
    if PIP_PATTERN.fullmatch(executable) and len(tokens) > 1 and tokens[1] == "install":
        if "--dry-run" not in tokens:
            return ReplayActionKind.PYTHON_PACKAGE_INSTALL
    if PYTHON_PATTERN.fullmatch(executable) and tokens[1:4] == ["-m", "pip", "install"]:
        if "--dry-run" not in tokens:
            return ReplayActionKind.PYTHON_PACKAGE_INSTALL
    if (
        PYTHON_PATTERN.fullmatch(executable)
        and len(tokens) > 3
        and tokens[1:3] == ["-m", "pdm"]
        and tokens[3] in {"install", "sync"}
        and "--dry-run" not in tokens
    ):
        return ReplayActionKind.PYTHON_PACKAGE_INSTALL
    if (
        executable == "pdm"
        and len(tokens) > 1
        and tokens[1] in {"install", "sync"}
        and "--dry-run" not in tokens
    ):
        return ReplayActionKind.PYTHON_PACKAGE_INSTALL
    if executable == "uv" and len(tokens) > 1:
        subcommand = tokens[1:3]
        if tokens[1] in {"add", "install", "sync"} or subcommand in (["pip", "install"], ["pip", "sync"]):
            return ReplayActionKind.PYTHON_PACKAGE_INSTALL
    if executable == "poetry" and len(tokens) > 1 and tokens[1] in {"add", "install"}:
        return ReplayActionKind.PYTHON_PACKAGE_INSTALL
    if executable in {"conda", "mamba", "micromamba"} and len(tokens) > 1:
        if tokens[1] in {"create", "install"} or tokens[1:3] == ["env", "create"]:
            return ReplayActionKind.PYTHON_PACKAGE_INSTALL
    if executable in {"apt", "apt-get", "apk", "brew", "dnf", "yum"} and len(tokens) > 1:
        if tokens[1] in {"install", "add"}:
            return ReplayActionKind.SYSTEM_PACKAGE_INSTALL
        if tokens[1] in {"update", "upgrade"}:
            return ReplayActionKind.PACKAGE_INDEX_UPDATE
    if executable == "pyenv" and len(tokens) > 1 and tokens[1] in {
        "global", "install", "local", "rehash", "shell"
    }:
        return ReplayActionKind.RUNTIME_CONFIGURE
    if executable == "hash" and tokens[1:] == ["-r"]:
        return ReplayActionKind.RUNTIME_CONFIGURE
    if executable == "export" and _valid_environment_export(tokens):
        return ReplayActionKind.ENVIRONMENT_EXPORT
    if executable in {"source", "."} and _valid_environment_activation(command, tokens):
        return ReplayActionKind.ENVIRONMENT_ACTIVATE
    return None


def _canonical_mutation(command: str) -> tuple[str, ReplayActionKind] | None:
    pipeline = _split_top_level(command, "|")
    if pipeline is None or not pipeline:
        return None
    base = pipeline[0].strip()
    base = re.sub(r"\s+2>&1\s*$", "", base).rstrip()
    kind = _classify_mutation(base)
    if kind is None:
        return None
    activation_with_known_substitution = (
        kind == ReplayActionKind.ENVIRONMENT_ACTIVATE
        and re.fullmatch(
            r"(?:source|\.)\s+\$\(poetry env info --path\)/bin/activate",
            base,
        )
    )
    if (
        any(marker in base for marker in SHELL_SUBSTITUTION_MARKERS)
        and not activation_with_known_substitution
    ):
        return None
    shell_tokens = _punctuated_tokens(base)
    if not shell_tokens or any(
        token in {"|", "||", "&&", ";", "&", "<", ">", ">>", ">&", "&>"}
        for token in shell_tokens
    ):
        return None
    for filter_command in pipeline[1:]:
        tokens = _tokens(filter_command)
        if not tokens or tokens[0] not in LOG_FILTERS:
            return None
    return base, kind


def _canonical_persistent_export(
    command: str,
) -> tuple[str, ReplayActionKind] | None:
    tokens = _punctuated_tokens(command)
    if (
        not tokens
        or len(tokens) != 4
        or tokens[0] != "echo"
        or tokens[2] != ">>"
        or tokens[3] not in SHELL_STARTUP_FILES
    ):
        return None
    payload = tokens[1]
    payload_tokens = _tokens(payload)
    if not payload_tokens or payload_tokens[0] != "export":
        return None
    if not _valid_environment_export(payload_tokens):
        return None
    return payload, ReplayActionKind.ENVIRONMENT_EXPORT


def _canonical_pyenv_initialization(
    command: str,
) -> tuple[str, ReplayActionKind] | None:
    if not re.fullmatch(
        r'''eval\s+(["'])\$\(\s*pyenv\s+init\s+(?:-|--path)\s*\)\1''',
        command,
    ):
        return None
    return 'export PATH="$(pyenv root)/shims:$PATH"', ReplayActionKind.RUNTIME_CONFIGURE


def _nested_shell_body(command: str) -> str | None:
    tokens = _tokens(command)
    if not tokens or len(tokens) != 3:
        return None
    executable = tokens[0].rsplit("/", 1)[-1]
    if executable not in {"bash", "sh"} or tokens[1] not in {"-c", "-lc"}:
        return None
    return tokens[2]


def _map_project_path(command: str, project_directory: str | None) -> tuple[str, bool]:
    if not project_directory:
        return command, False
    source = f"/data/project/{project_directory}"
    if source not in command:
        return command, False
    return command.replace(source, '"${PROJECT_ROOT}"'), True


def _valid_working_directory(command: str) -> bool:
    tokens = _tokens(command)
    if not tokens or len(tokens) != 2 or tokens[0] != "cd":
        return False
    target = tokens[1]
    if target == "${PROJECT_ROOT}":
        return True
    path_parts = target.split("/")
    return not target.startswith("/") and ".." not in path_parts


def analyze_successful_command(
    command: str,
    project_directory: str | None = None,
) -> CommandAnalysis:
    mapped, project_path_mapped = _map_project_path(command, project_directory)
    semicolon_parts = _split_top_level(mapped, ";")
    if semicolon_parts is None:
        return CommandAnalysis(unsupported_reason="unbalanced shell syntax")
    if len(semicolon_parts) > 1:
        analyses = [analyze_successful_command(part, None) for part in semicolon_parts if part]
        if analyses and all(item.dropped and not item.unsupported_reason for item in analyses):
            return CommandAnalysis(dropped=True, project_path_mapped=project_path_mapped)
        return CommandAnalysis(unsupported_reason="top-level semicolon compound command")
    fallback_parts = _split_top_level(mapped, "||")
    if fallback_parts is None:
        return CommandAnalysis(unsupported_reason="unbalanced shell syntax")
    if len(fallback_parts) > 1:
        analyses = [
            analyze_successful_command(part, None) for part in fallback_parts if part
        ]
        if analyses and all(
            item.dropped and not item.unsupported_reason for item in analyses
        ):
            return CommandAnalysis(
                dropped=True,
                project_path_mapped=project_path_mapped,
            )
        return CommandAnalysis(
            unsupported_reason="fallback expression is not entirely observational"
        )
    if "\n" in mapped:
        multiline_parts = _split_top_level(mapped, "\n")
        if multiline_parts is None:
            return CommandAnalysis(unsupported_reason="unbalanced shell syntax")
        if len(multiline_parts) > 1:
            analyses = [
                analyze_successful_command(part, None)
                for part in multiline_parts
                if part
            ]
            if analyses and all(
                item.dropped and not item.unsupported_reason for item in analyses
            ):
                return CommandAnalysis(
                    dropped=True,
                    project_path_mapped=project_path_mapped,
                )
            return CommandAnalysis(
                unsupported_reason="top-level multiline command"
            )

    segments = _split_top_level(mapped, "&&")
    if segments is None:
        return CommandAnalysis(unsupported_reason="unbalanced shell syntax")
    actions: list[ReplayAction] = []
    working_directory: str | None = None
    for segment in segments:
        if not segment:
            return CommandAnalysis(unsupported_reason="empty shell segment")
        if segment.lstrip().startswith("cd "):
            if not _valid_working_directory(segment):
                return CommandAnalysis(unsupported_reason=f"unsupported working directory: {segment}")
            working_directory = segment
            continue
        nested_body = _nested_shell_body(segment)
        if nested_body is not None:
            nested = analyze_successful_command(nested_body)
            if nested.dropped and not nested.unsupported_reason:
                continue
            return CommandAnalysis(
                unsupported_reason="nested shell is not entirely observational"
            )
        if _is_observation(segment):
            continue
        mutation = (
            _canonical_pyenv_initialization(segment)
            or _canonical_persistent_export(segment)
            or _canonical_mutation(segment)
        )
        if mutation is None:
            return CommandAnalysis(unsupported_reason=f"unknown successful shell segment: {segment}")
        replay_command, kind = mutation
        if working_directory:
            replay_command = f"{working_directory} && {replay_command}"
        actions.append(ReplayAction(kind.value, replay_command, command))
        working_directory = None
    return CommandAnalysis(
        actions=tuple(actions),
        dropped=not actions,
        project_path_mapped=project_path_mapped,
    )
