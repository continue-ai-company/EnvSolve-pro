from __future__ import annotations

from pathlib import PurePosixPath
import re

from envsolve.solver import CandidateValidation, DeploymentCandidate


OPEN_PROGRAM_POLICY = "open-candidate-program-v1"
_IMPORTABLE_SUFFIXES = (".py", ".pyi", ".pyc", ".pyd", ".so", ".pth")
_ALLOWED_BUILD_DRIVER_NAMES = {"setup.py"}
_OUTPUT_REDIRECTION = re.compile(
    r"(?<!>)>>?\s*(?P<target>\"[^\"\n]+\"|'[^'\n]+'|[^\s;|]+)"
)
_DIRECT_FILE_COMMAND = re.compile(
    r"(?:^|(?:&&|\|\||[;|])\s*)"
    r"(?:touch|truncate|cp|mv|install|tee)\s+(?P<arguments>[^;&|]+)"
)
_QUOTED_IMPORT_ARTIFACT = re.compile(
    r"""["'](?P<target>[^"'\n]+\.(?:py|pyi|pyc|pyd|so|pth))["']""",
    re.IGNORECASE,
)
_EMBEDDED_FILE_WRITE = re.compile(
    r"""
    \bopen\s*\([^)]*,\s*["'][^"']*[wax+][^"']*["']
    |\.open\s*\(\s*["'][^"']*[wax+][^"']*["']
    |\.write\s*\(
    |\.(?:write_text|write_bytes|touch)\s*\(
    |\b(?:shutil\.)?(?:copy|copyfile|move)\s*\(
    |\bos\.(?:mknod|rename|replace)\s*\(
    """,
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)


def _normalized_shell_target(value: str) -> str:
    return value.strip().strip("\"'")


def _direct_import_artifact(value: str) -> str | None:
    target = _normalized_shell_target(value)
    name = PurePosixPath(target).name
    if name in _ALLOWED_BUILD_DRIVER_NAMES:
        return None
    return target if name.lower().endswith(_IMPORTABLE_SUFFIXES) else None


def _direct_import_artifact_write(script: str) -> tuple[str, str] | None:
    for line in script.splitlines():
        for match in _OUTPUT_REDIRECTION.finditer(line):
            target = _direct_import_artifact(match.group("target"))
            if target is not None:
                return line.strip(), target
        for match in _DIRECT_FILE_COMMAND.finditer(line):
            for token in re.findall(
                r"\"[^\"\n]+\"|'[^'\n]+'|[^\s]+",
                match.group("arguments"),
            ):
                target = _direct_import_artifact(token)
                if target is not None:
                    return line.strip(), target
    return None


def _embedded_import_artifact_write(script: str) -> tuple[str, str] | None:
    if _EMBEDDED_FILE_WRITE.search(script) is None:
        return None
    for match in _QUOTED_IMPORT_ARTIFACT.finditer(script):
        target = _direct_import_artifact(match.group("target"))
        if target is None:
            continue
        line_start = script.rfind("\n", 0, match.start()) + 1
        line_end = script.find("\n", match.end())
        if line_end < 0:
            line_end = len(script)
        return script[line_start:line_end].strip(), target
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
for commands that run after it.
Environment-path configuration may expose real repository or installed artifacts,
but must not point to synthetic modules or shadow the executable goal.
Do not directly create or copy Python import artifacts such as `.py`, `.pyi`, `.pth`,
or `.so` files. Use repository build and package tools to materialize real artifacts;
a temporary `setup.py` may be used only as a build driver.

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
