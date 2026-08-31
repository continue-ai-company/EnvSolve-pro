from __future__ import annotations

import ast
from pathlib import PurePosixPath
import re
import shlex
from typing import Iterator

from envsolve.solver import CandidateValidation, DeploymentCandidate


OPEN_PROGRAM_POLICY = "open-candidate-program-v2"
_IMPORTABLE_SUFFIXES = (".py", ".pyi", ".pyc", ".pyd", ".so", ".pth")
_ALLOWED_BUILD_DRIVER_NAMES = {"setup.py"}
_OUTPUT_REDIRECTION = re.compile(
    r"(?<!>)>>?\s*(?P<target>\"[^\"\n]+\"|'[^'\n]+'|[^\s;|]+)"
)
_DIRECT_FILE_COMMAND = re.compile(
    r"(?:^|(?:&&|\|\||[;|])\s*)"
    r"(?P<command>touch|truncate|cp|mv|install|tee)\s+"
    r"(?P<arguments>[^;&|]+)"
)
_SYMLINK_COMMAND = re.compile(
    r"(?:^|(?:&&|\|\||[;|])\s*|\bthen\s+)\s*"
    r"ln\s+(?P<arguments>[^;&|]+)",
)
_IMPORT_SEARCH_PATH_TOKENS = (
    "site-packages",
    "dist-packages",
    "site_packages",
    "sitepackages",
    "getsitepackages",
    "purelib",
    "platlib",
)


def _normalized_shell_target(value: str) -> str:
    return value.strip().strip("\"'")


def _direct_import_artifact(value: str) -> str | None:
    target = _normalized_shell_target(value)
    name = PurePosixPath(target).name
    if name in _ALLOWED_BUILD_DRIVER_NAMES:
        return None
    return target if name.lower().endswith(_IMPORTABLE_SUFFIXES) else None


def _is_repository_template_copy(command: str, arguments: str) -> bool:
    if command != "cp":
        return False
    try:
        tokens = shlex.split(arguments, posix=True)
    except ValueError:
        return False
    operands = [token for token in tokens if not token.startswith("-")]
    if len(operands) != 2:
        return False
    source = PurePosixPath(_normalized_shell_target(operands[0]))
    destination = PurePosixPath(_normalized_shell_target(operands[1]))
    return (
        source.parent == destination.parent
        and source.stem == destination.stem
        and source.suffix.lower() not in _IMPORTABLE_SUFFIXES
        and destination.suffix.lower() in _IMPORTABLE_SUFFIXES
    )


def _direct_import_artifact_write(script: str) -> tuple[str, str] | None:
    for line in script.splitlines():
        for match in _OUTPUT_REDIRECTION.finditer(line):
            target = _direct_import_artifact(match.group("target"))
            if target is not None:
                return line.strip(), target
        for match in _DIRECT_FILE_COMMAND.finditer(line):
            if _is_repository_template_copy(
                match.group("command"),
                match.group("arguments"),
            ):
                continue
            for token in re.findall(
                r"\"[^\"\n]+\"|'[^'\n]+'|[^\s]+",
                match.group("arguments"),
            ):
                target = _direct_import_artifact(token)
                if target is not None:
                    return line.strip(), target
    return None


def _embedded_python_snippets(script: str) -> Iterator[tuple[str, int]]:
    lines = script.splitlines()
    index = 0
    while index < len(lines):
        match = re.search(
            r"<<-?\s*(?P<quote>['\"]?)(?P<marker>[A-Za-z_][A-Za-z0-9_]*)"
            r"(?P=quote)",
            lines[index],
        )
        if match is None:
            index += 1
            continue
        marker = match.group("marker")
        end = index + 1
        while end < len(lines) and lines[end].lstrip("\t").strip() != marker:
            end += 1
        if end >= len(lines):
            index += 1
            continue
        yield "\n".join(lines[index + 1 : end]), index + 2
        index = end + 1

    for line_number, line in enumerate(lines, start=1):
        try:
            tokens = shlex.split(line, posix=True)
        except ValueError:
            continue
        for position, token in enumerate(tokens[:-1]):
            executable = PurePosixPath(token).name
            if not re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", executable):
                continue
            try:
                command_position = tokens.index("-c", position + 1)
            except ValueError:
                continue
            if command_position + 1 >= len(tokens):
                continue
            yield tokens[command_position + 1], line_number


def _joined_string(node: ast.JoinedStr) -> str:
    return "".join(
        item.value if isinstance(item, ast.Constant) else "{...}"
        for item in node.values
        if isinstance(item, (ast.Constant, ast.FormattedValue))
    )


def _expression_import_artifact(
    node: ast.AST,
    assignments: dict[str, ast.AST],
    *,
    seen: frozenset[str] = frozenset(),
) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return _direct_import_artifact(node.value)
    if isinstance(node, ast.JoinedStr):
        return _direct_import_artifact(_joined_string(node))
    if isinstance(node, ast.Name):
        if node.id in seen or node.id not in assignments:
            return None
        return _expression_import_artifact(
            assignments[node.id],
            assignments,
            seen=seen | {node.id},
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Div)):
        return _expression_import_artifact(
            node.right,
            assignments,
            seen=seen,
        ) or _expression_import_artifact(node.left, assignments, seen=seen)
    if not isinstance(node, ast.Call):
        return None
    function = node.func
    if (
        isinstance(function, ast.Attribute)
        and function.attr == "with_suffix"
        and node.args
    ):
        suffix = node.args[0]
        if isinstance(suffix, ast.Constant) and isinstance(suffix.value, str):
            return _direct_import_artifact(f"artifact{suffix.value}")
    path_constructor = (
        isinstance(function, ast.Name)
        and function.id in {"Path", "PurePath", "PurePosixPath"}
    )
    path_join = isinstance(function, ast.Attribute) and function.attr in {
        "join",
        "joinpath",
    }
    if path_constructor or path_join:
        for argument in reversed(node.args):
            target = _expression_import_artifact(
                argument,
                assignments,
                seen=seen,
            )
            if target is not None:
                return target
    return None


def _literal_write_mode(node: ast.AST | None) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and any(flag in node.value for flag in "wax+")
    )


def _call_write_target(node: ast.Call) -> ast.AST | None:
    function = node.func
    if isinstance(function, ast.Name) and function.id == "open":
        mode = node.args[1] if len(node.args) > 1 else None
        mode = next(
            (
                keyword.value
                for keyword in node.keywords
                if keyword.arg == "mode"
            ),
            mode,
        )
        return node.args[0] if node.args and _literal_write_mode(mode) else None
    if not isinstance(function, ast.Attribute):
        return None
    if function.attr in {"write_text", "write_bytes", "touch"}:
        return function.value
    if function.attr == "open":
        mode = node.args[0] if node.args else None
        mode = next(
            (
                keyword.value
                for keyword in node.keywords
                if keyword.arg == "mode"
            ),
            mode,
        )
        return function.value if _literal_write_mode(mode) else None
    if function.attr in {"copy", "copyfile", "move", "rename", "replace"}:
        return node.args[-1] if len(node.args) >= 2 else None
    if function.attr == "mknod":
        return node.args[0] if node.args else None
    return None


def _embedded_import_artifact_write(script: str) -> tuple[str, str] | None:
    for source, _line_offset in _embedded_python_snippets(script):
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        assignments: dict[str, ast.AST] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            write_target = _call_write_target(node)
            if write_target is None:
                continue
            target = _expression_import_artifact(write_target, assignments)
            if target is None:
                continue
            source_line = source.splitlines()[node.lineno - 1].strip()
            return source_line, target
    return None


def _symbolic_link_import_alias(script: str) -> tuple[str, str] | None:
    import_path_variables = {
        match.group("name").lower()
        for match in re.finditer(
            r"(?m)^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>[^\n]+)$",
            script,
        )
        if any(
            token in match.group("value").lower()
            for token in _IMPORT_SEARCH_PATH_TOKENS
        )
    }
    for line in script.splitlines():
        for match in _SYMLINK_COMMAND.finditer(line):
            tokens = re.findall(
                r"\"[^\"\n]+\"|'[^'\n]+'|[^\s]+",
                match.group("arguments"),
            )
            options = [token for token in tokens if token.startswith("-")]
            symbolic = any(
                token in {"--symbolic", "--symbolic-link"}
                or (
                    token.startswith("-")
                    and not token.startswith("--")
                    and "s" in token[1:]
                )
                for token in options
            )
            operands = [token for token in tokens if not token.startswith("-")]
            if not symbolic or len(operands) < 2:
                continue
            destination = _normalized_shell_target(operands[-1])
            lowered = destination.lower()
            variable_target = any(
                f"${name}" in lowered or f"${{{name}}}" in lowered
                for name in import_path_variables
            )
            if variable_target or any(
                token in lowered for token in _IMPORT_SEARCH_PATH_TOKENS
            ):
                return line.strip(), destination
    return None


class OpenCandidateProgramValidator:
    """Admit complete shell programs; execution effects determine validity."""

    policy_id = OPEN_PROGRAM_POLICY
    prompt_contract = """\
Return one complete, self-contained Bash program that will be inserted inline into
the controlling Bash process from the project root in a fresh container. No
harness-specific project-root environment variable is defined during the candidate;
use `$PWD` when an absolute project path is needed. You may use normal Bash
composition and control flow, but do not terminate or replace the controlling shell
with `exit`, `return`, or `exec`. Do not edit tracked repository files, inject
importable source files, suppress the terminal verifier, or delete evaluator-owned
workspace artifacts. The program must leave the selected Python environment active
for commands that run after it. It may change directories temporarily, but it must
return the controlling shell to its starting project root before it finishes.
Environment-path configuration may expose real repository or installed artifacts,
but must not point to synthetic modules or shadow the executable goal.
Do not directly create or copy Python import artifacts such as `.py`, `.pyi`, `.pth`,
or `.so` files. The only direct-copy exception is a same-directory, same-stem target
copied from a repository-tracked non-importable template; the target must already be
ignored by the repository and remain byte-identical to that template. Do not create
import aliases by symlinking repository paths into Python package search directories.
Use repository build and package tools to materialize real artifacts; a temporary
`setup.py` may be used only as a build driver.

Shell syntax is not restricted to a command schema. Safety and correctness are
decided by isolated execution, repository-effect audit, and executable postconditions.
""".strip()

    def __init__(self, max_chars: int = 100_000) -> None:
        if max_chars <= 0:
            raise ValueError("Open candidate size bound must be positive")
        self.max_chars = max_chars

    def validate(self, candidate: DeploymentCandidate) -> CandidateValidation:
        script = candidate.script.replace("\r\n", "\n").replace("\r", "\n")
        if "\x00" in script:
            return CandidateValidation(
                False,
                self.policy_id,
                reason="candidate program contains a NUL byte",
            )
        normalized = script.rstrip() + "\n"
        if len(normalized) > self.max_chars:
            return CandidateValidation(
                False,
                self.policy_id,
                reason="candidate program exceeds the fixed size bound",
                details={
                    "max_chars": self.max_chars,
                    "observed_chars": len(normalized),
                },
            )
        direct_artifact = _direct_import_artifact_write(script)
        if direct_artifact is not None:
            line, target = direct_artifact
            return CandidateValidation(
                False,
                self.policy_id,
                reason=(
                    "candidate program directly materializes an importable artifact"
                ),
                details={"line": line, "target": target},
            )
        embedded_artifact = _embedded_import_artifact_write(script)
        if embedded_artifact is not None:
            line, target = embedded_artifact
            return CandidateValidation(
                False,
                self.policy_id,
                reason=(
                    "candidate program embeds code that materializes an "
                    "importable artifact"
                ),
                details={"line": line, "target": target},
            )
        import_alias = _symbolic_link_import_alias(script)
        if import_alias is not None:
            line, target = import_alias
            return CandidateValidation(
                False,
                self.policy_id,
                reason=(
                    "candidate program creates a symbolic link in a Python "
                    "import search directory"
                ),
                details={"line": line, "target": target},
            )
        executable_lines = [
            line
            for line in script.splitlines()
            if line.strip()
            and not line.lstrip().startswith("#")
        ]
        if not executable_lines:
            return CandidateValidation(
                False,
                self.policy_id,
                reason="candidate program contains no executable shell statement",
            )
        return CandidateValidation(
            True,
            self.policy_id,
            normalized_script=normalized,
            details={
                "interface": OPEN_PROGRAM_POLICY,
                "script_chars": len(normalized),
                "safety_boundary": "fresh-container+effect-audit+postconditions",
            },
        )
