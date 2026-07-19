from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any


ALLOWED_GENERATED_DIRECTORIES = {
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "venv",
}
ALLOWED_GENERATED_FILES = {".coverage", "coverage.xml"}
CONFIGURATION_NAMES = {
    "Pipfile",
    "Pipfile.lock",
    "environment.yml",
    "poetry.lock",
    "pyproject.toml",
    "pyrightconfig.json",
    "requirements.txt",
    "setup.cfg",
    "setup.py",
    "tox.ini",
    "uv.lock",
}
IMPORTABLE_SUFFIXES = {".pth", ".py", ".pyc", ".pyi", ".pyd", ".so"}


@dataclass(frozen=True)
class IntegrityViolation:
    kind: str
    path: str | None
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RepositoryIntegrityReport:
    expected_revision: str
    checked_out_revision: str | None
    tracked_changes: tuple[str, ...]
    allowed_generated_paths: tuple[str, ...]
    disallowed_untracked_paths: tuple[str, ...]
    violations: tuple[IntegrityViolation, ...]

    @property
    def valid(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": "clean-tree-generated-artifacts-v1",
            "valid": self.valid,
            "expected_revision": self.expected_revision,
            "checked_out_revision": self.checked_out_revision,
            "tracked_changes": list(self.tracked_changes),
            "allowed_generated_paths": list(self.allowed_generated_paths),
            "disallowed_untracked_paths": list(self.disallowed_untracked_paths),
            "violations": [violation.to_dict() for violation in self.violations],
        }


def _git(repo_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )


def _nul_paths(value: str) -> tuple[str, ...]:
    return tuple(sorted(path for path in value.split("\0") if path))


def _is_allowed_generated(path: str) -> bool:
    pure = PurePosixPath(path)
    if pure.name in ALLOWED_GENERATED_FILES:
        return True
    return any(
        part in ALLOWED_GENERATED_DIRECTORIES or part.endswith(".egg-info")
        for part in pure.parts
    )


def _untracked_violation(repo_path: Path, path: str) -> IntegrityViolation:
    candidate = repo_path / path
    pure = PurePosixPath(path)
    if candidate.is_symlink():
        return IntegrityViolation("untracked_symlink", path, "untracked symlinks are prohibited")
    if pure.suffix.lower() in IMPORTABLE_SUFFIXES:
        return IntegrityViolation(
            "untracked_import_artifact",
            path,
            "untracked importable files and .pth files are prohibited",
        )
    if pure.name in CONFIGURATION_NAMES or pure.name.startswith("requirements-"):
        return IntegrityViolation(
            "untracked_configuration",
            path,
            "untracked build, dependency, or verifier configuration is prohibited",
        )
    return IntegrityViolation(
        "untracked_repository_output",
        path,
        "untracked files outside generated-artifact directories are prohibited",
    )


def inspect_repository(repo_path: Path, expected_revision: str) -> RepositoryIntegrityReport:
    violations: list[IntegrityViolation] = []
    head = _git(repo_path, "rev-parse", "HEAD")
    checked_out_revision = head.stdout.strip() if head.returncode == 0 else None
    if head.returncode != 0:
        violations.append(IntegrityViolation("git_error", None, head.stderr.strip()))
    elif checked_out_revision != expected_revision:
        violations.append(
            IntegrityViolation(
                "revision_mismatch",
                None,
                f"checked out {checked_out_revision}, expected {expected_revision}",
            )
        )

    unstaged = _git(repo_path, "diff", "--name-only", "-z", "HEAD", "--")
    staged = _git(repo_path, "diff", "--cached", "--name-only", "-z", "HEAD", "--")
    tracked_changes = _nul_paths(unstaged.stdout + staged.stdout)
    for process, label in ((unstaged, "unstaged diff"), (staged, "staged diff")):
        if process.returncode != 0:
            violations.append(IntegrityViolation("git_error", None, f"{label}: {process.stderr.strip()}"))
    violations.extend(
        IntegrityViolation("tracked_change", path, "tracked repository files must remain unchanged")
        for path in tracked_changes
    )

    untracked_process = _git(repo_path, "ls-files", "--others", "--exclude-standard", "-z")
    ignored_process = _git(
        repo_path,
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
        "-z",
    )
    untracked = _nul_paths(untracked_process.stdout + ignored_process.stdout)
    if untracked_process.returncode != 0 or ignored_process.returncode != 0:
        violations.append(
            IntegrityViolation(
                "git_error",
                None,
                f"untracked files: {untracked_process.stderr.strip()} {ignored_process.stderr.strip()}",
            )
        )
    allowed = tuple(path for path in untracked if _is_allowed_generated(path))
    disallowed = tuple(path for path in untracked if not _is_allowed_generated(path))
    violations.extend(_untracked_violation(repo_path, path) for path in disallowed)

    return RepositoryIntegrityReport(
        expected_revision=expected_revision,
        checked_out_revision=checked_out_revision,
        tracked_changes=tracked_changes,
        allowed_generated_paths=allowed,
        disallowed_untracked_paths=disallowed,
        violations=tuple(violations),
    )
