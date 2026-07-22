from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any

from envsolve.runtime.workspace import WorkspacePrecondition


ALLOWED_GENERATED_DIRECTORIES = {
    ".mypy_cache",
    ".nox",
    ".pnpm-store",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".turbo",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "node_modules",
    "venv",
}
ALLOWED_GENERATED_PATH_SAMPLE_LIMIT = 256
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
    allowed_generated_path_count: int
    disallowed_untracked_paths: tuple[str, ...]
    violations: tuple[IntegrityViolation, ...]

    @property
    def valid(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": "clean-tracked-tree-and-no-untracked-injection-v3",
            "valid": self.valid,
            "expected_revision": self.expected_revision,
            "checked_out_revision": self.checked_out_revision,
            "tracked_changes": list(self.tracked_changes),
            "allowed_generated_paths": list(self.allowed_generated_paths),
            "allowed_generated_path_count": self.allowed_generated_path_count,
            "allowed_generated_paths_truncated": (
                self.allowed_generated_path_count > len(self.allowed_generated_paths)
            ),
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


def _is_virtual_environment(root: Path) -> bool:
    configuration = root / "pyvenv.cfg"
    activate = root / "bin/activate"
    python = root / "bin/python"
    if (
        not configuration.is_file()
        or configuration.is_symlink()
        or not activate.is_file()
        or activate.is_symlink()
        or not (python.is_file() or python.is_symlink())
    ):
        return False
    try:
        fields = {
            key.strip().lower(): value.strip()
            for line in configuration.read_text(encoding="utf-8").splitlines()
            if "=" in line
            for key, value in [line.split("=", 1)]
        }
    except (OSError, UnicodeError):
        return False
    return "home" in fields and "include-system-site-packages" in fields


def _virtual_environment_roots(
    repo_path: Path,
    paths: tuple[str, ...],
) -> tuple[PurePosixPath, ...]:
    candidates = {
        PurePosixPath(path).parent
        for path in paths
        if PurePosixPath(path).name == "pyvenv.cfg"
        and len(PurePosixPath(path).parts) > 1
    }
    return tuple(
        sorted(root for root in candidates if _is_virtual_environment(repo_path / root))
    )


def _inside_root(path: PurePosixPath, root: PurePosixPath) -> bool:
    return path == root or root in path.parents


def _is_allowed_generated(
    path: str,
    virtual_environment_roots: tuple[PurePosixPath, ...] = (),
) -> bool:
    pure = PurePosixPath(path)
    if any(_inside_root(pure, root) for root in virtual_environment_roots):
        return True
    if pure.name in ALLOWED_GENERATED_FILES:
        return True
    return any(
        part in ALLOWED_GENERATED_DIRECTORIES or part.endswith(".egg-info")
        for part in pure.parts
    )


def _generated_root(
    path: str,
    virtual_environment_roots: tuple[PurePosixPath, ...] = (),
) -> str | None:
    pure = PurePosixPath(path)
    for root in virtual_environment_roots:
        if _inside_root(pure, root):
            return str(root) + "/"
    for index, part in enumerate(pure.parts):
        if part in ALLOWED_GENERATED_DIRECTORIES or part.endswith(".egg-info"):
            return "/".join(pure.parts[: index + 1]) + "/"
    return path if pure.name in ALLOWED_GENERATED_FILES else None


def _untracked_violation(
    repo_path: Path,
    path: str,
) -> IntegrityViolation | None:
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
    return None


def inspect_repository(
    repo_path: Path,
    expected_revision: str,
    required_preconditions: tuple[WorkspacePrecondition, ...] = (),
) -> RepositoryIntegrityReport:
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
    virtual_environment_roots = _virtual_environment_roots(repo_path, untracked)
    if untracked_process.returncode != 0 or ignored_process.returncode != 0:
        violations.append(
            IntegrityViolation(
                "git_error",
                None,
                f"untracked files: {untracked_process.stderr.strip()} {ignored_process.stderr.strip()}",
            )
        )
    untracked_violations = {
        path: violation
        for path in untracked
        if not _is_allowed_generated(path, virtual_environment_roots)
        for violation in [_untracked_violation(repo_path, path)]
        if violation is not None
    }
    allowed = tuple(
        sorted(
            {
                _generated_root(path, virtual_environment_roots) or path
                for path in untracked
                if path not in untracked_violations
            }
        )
    )
    allowed_sample = allowed[:ALLOWED_GENERATED_PATH_SAMPLE_LIMIT]
    disallowed = tuple(path for path in untracked if path in untracked_violations)
    violations.extend(untracked_violations[path] for path in disallowed)
    violations.extend(
        IntegrityViolation(
            "workspace_precondition_missing",
            precondition.path,
            (
                f"{precondition.kind} owned by {precondition.producer} must remain "
                "present after candidate execution"
            ),
        )
        for precondition in required_preconditions
        if not precondition.satisfied_by(repo_path)
    )

    return RepositoryIntegrityReport(
        expected_revision=expected_revision,
        checked_out_revision=checked_out_revision,
        tracked_changes=tracked_changes,
        allowed_generated_paths=allowed_sample,
        allowed_generated_path_count=len(allowed),
        disallowed_untracked_paths=disallowed,
        violations=tuple(violations),
    )
