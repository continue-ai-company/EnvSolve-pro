from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any

from envsolve.runtime.workspace import WorkspacePrecondition

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python < 3.11
    import tomli as tomllib


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
    "target",
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
COMPILED_EXTENSION_SUFFIXES = {".pyd", ".so"}


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
    declared_generated_paths: tuple[str, ...]
    allowed_generated_paths: tuple[str, ...]
    allowed_generated_path_count: int
    disallowed_untracked_paths: tuple[str, ...]
    violations: tuple[IntegrityViolation, ...]

    @property
    def valid(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": "clean-tracked-tree-and-declared-generated-files-v5",
            "valid": self.valid,
            "expected_revision": self.expected_revision,
            "checked_out_revision": self.checked_out_revision,
            "tracked_changes": list(self.tracked_changes),
            "declared_generated_paths": list(self.declared_generated_paths),
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
    try:
        valid_layout = (
            configuration.is_file()
            and not configuration.is_symlink()
            and activate.is_file()
            and not activate.is_symlink()
            # Container-created environments can use absolute links whose targets
            # are inaccessible or absent on the host running the effect audit.
            and (python.is_symlink() or python.is_file())
        )
    except OSError:
        return False
    if not valid_layout:
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


def _safe_relative_path(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = PurePosixPath(value)
    if (
        candidate.is_absolute()
        or not candidate.parts
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        return None
    return str(candidate)


def _declared_generated_paths(repo_path: Path) -> tuple[str, ...]:
    """Read build-backend output paths that are explicit repository facts."""

    pyproject = repo_path / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        return ()
    tool = data.get("tool")
    setuptools_scm = tool.get("setuptools_scm") if isinstance(tool, dict) else None
    if not isinstance(setuptools_scm, dict):
        return ()
    return tuple(
        sorted(
            {
                path
                for key in ("version_file", "write_to")
                if (path := _safe_relative_path(setuptools_scm.get(key))) is not None
            }
        )
    )


def _is_allowed_generated(
    path: str,
    virtual_environment_roots: tuple[PurePosixPath, ...] = (),
    declared_generated_paths: tuple[str, ...] = (),
    ignored_paths: frozenset[str] = frozenset(),
) -> bool:
    pure = PurePosixPath(path)
    if any(_inside_root(pure, root) for root in virtual_environment_roots):
        return True
    if path in declared_generated_paths and path in ignored_paths:
        return True
    if path in ignored_paths and pure.suffix.lower() in COMPILED_EXTENSION_SUFFIXES:
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
    declared_generated_paths: tuple[str, ...] = (),
) -> str | None:
    pure = PurePosixPath(path)
    for root in virtual_environment_roots:
        if _inside_root(pure, root):
            return str(root) + "/"
    if path in declared_generated_paths:
        return path
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
    ignored_paths = frozenset(_nul_paths(ignored_process.stdout))
    virtual_environment_roots = _virtual_environment_roots(repo_path, untracked)
    declared_generated_paths = _declared_generated_paths(repo_path)
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
        if not _is_allowed_generated(
            path,
            virtual_environment_roots,
            declared_generated_paths,
            ignored_paths,
        )
        for violation in [_untracked_violation(repo_path, path)]
        if violation is not None
    }
    allowed = tuple(
        sorted(
            {
                _generated_root(
                    path,
                    virtual_environment_roots,
                    declared_generated_paths,
                )
                or path
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
        declared_generated_paths=declared_generated_paths,
        allowed_generated_paths=allowed_sample,
        allowed_generated_path_count=len(allowed),
        disallowed_untracked_paths=disallowed,
        violations=tuple(violations),
    )
