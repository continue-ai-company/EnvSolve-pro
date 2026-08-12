from __future__ import annotations

import base64
import binascii
import csv
from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
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
REPOSITORY_TEMPLATE_MARKERS = ("dist", "example", "sample", "template")


@dataclass(frozen=True)
class IntegrityViolation:
    kind: str
    path: str | None
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RepositoryDerivedArtifact:
    path: str
    source_path: str
    sha256: str
    derivation: str = "exact-copy-of-tracked-sibling-template"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class RepositoryIntegrityReport:
    expected_revision: str
    checked_out_revision: str | None
    tracked_changes: tuple[str, ...]
    declared_generated_paths: tuple[str, ...]
    allowed_generated_paths: tuple[str, ...]
    allowed_generated_path_count: int
    repository_derived_artifacts: tuple[RepositoryDerivedArtifact, ...]
    disallowed_untracked_paths: tuple[str, ...]
    violations: tuple[IntegrityViolation, ...]

    @property
    def valid(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": "clean-tracked-tree-and-provenance-derived-files-v8",
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
            "repository_derived_artifacts": [
                artifact.to_dict()
                for artifact in self.repository_derived_artifacts
            ],
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


def _git_bytes(repo_path: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=False,
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


def _is_conda_environment(root: Path) -> bool:
    metadata = root / "conda-meta"
    history_path = metadata / "history"
    python = root / "bin/python"
    try:
        valid_layout = (
            history_path.is_file()
            and not history_path.is_symlink()
            and (python.is_symlink() or python.is_file())
        )
    except OSError:
        return False
    if not valid_layout:
        return False
    try:
        history = history_path.read_text(encoding="utf-8")
        records = sorted(metadata.glob("*.json"))
    except (OSError, UnicodeError):
        return False
    if "# cmd:" not in history or not records:
        return False

    for record_path in records[:64]:
        try:
            if record_path.is_symlink() or not record_path.is_file():
                continue
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict):
            continue
        name = record.get("name")
        version = record.get("version")
        build = record.get("build")
        files = record.get("files")
        if not all(isinstance(value, str) and value for value in (name, version, build)):
            continue
        if not isinstance(files, list) or not files:
            continue
        if f"::{name}-{version}-{build}" not in history:
            continue
        for value in files:
            relative = _safe_relative_path(value)
            if relative is None:
                continue
            installed = root / relative
            try:
                if installed.is_symlink() or installed.is_file():
                    return True
            except OSError:
                continue
    return False


def _conda_environment_roots(
    repo_path: Path,
    paths: tuple[str, ...],
) -> tuple[PurePosixPath, ...]:
    candidates = {
        PurePosixPath(path).parent.parent
        for path in paths
        if PurePosixPath(path).name == "history"
        and PurePosixPath(path).parent.name == "conda-meta"
        and len(PurePosixPath(path).parts) > 2
    }
    return tuple(
        sorted(root for root in candidates if _is_conda_environment(repo_path / root))
    )


def _environment_roots(
    repo_path: Path,
    paths: tuple[str, ...],
) -> tuple[PurePosixPath, ...]:
    return tuple(
        sorted(
            {
                *_virtual_environment_roots(repo_path, paths),
                *_conda_environment_roots(repo_path, paths),
            }
        )
    )


def _record_digest_matches(path: Path, digest: str, size: str) -> bool:
    try:
        expected_size = int(size)
        algorithm, encoded = digest.split("=", 1)
        expected_digest = base64.urlsafe_b64decode(
            encoded + "=" * (-len(encoded) % 4)
        )
        hasher = hashlib.new(algorithm)
        payload = path.read_bytes()
    except (OSError, ValueError, TypeError, binascii.Error):
        return False
    hasher.update(payload)
    return len(payload) == expected_size and hmac.compare_digest(
        hasher.digest(), expected_digest
    )


def _is_verified_setuptools_egg(root: Path) -> bool:
    """Recognize an unpacked wheel cached by setuptools without trusting its name."""

    metadata = root / "EGG-INFO"
    record_path = metadata / "RECORD"
    try:
        if (
            root.is_symlink()
            or not root.is_dir()
            or not (metadata / "PKG-INFO").is_file()
            or not (metadata / "WHEEL").is_file()
            or record_path.is_symlink()
            or not record_path.is_file()
        ):
            return False
        records = {
            relative: (digest, size)
            for row in csv.reader(record_path.read_text(encoding="utf-8").splitlines())
            if len(row) == 3
            for relative, digest, size in [row]
            if _safe_relative_path(relative) is not None
        }
        importable_files = tuple(
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in IMPORTABLE_SUFFIXES
            and "__pycache__" not in path.relative_to(root).parts
        )
    except (OSError, UnicodeError, csv.Error):
        return False
    if not importable_files:
        return False
    for path in importable_files:
        try:
            if path.is_symlink():
                return False
            relative = path.relative_to(root).as_posix()
        except (OSError, ValueError):
            return False
        digest_and_size = records.get(relative)
        if (
            digest_and_size is None
            or not all(digest_and_size)
            or not _record_digest_matches(path, *digest_and_size)
        ):
            return False
    return True


def _setuptools_egg_roots(
    repo_path: Path,
    paths: tuple[str, ...],
) -> tuple[PurePosixPath, ...]:
    candidates: set[PurePosixPath] = set()
    for path in paths:
        parts = PurePosixPath(path).parts
        for index, part in enumerate(parts[:-1]):
            if part == ".eggs" and parts[index + 1].endswith(".egg"):
                candidates.add(PurePosixPath(*parts[: index + 2]))
                break
    return tuple(
        sorted(
            root
            for root in candidates
            if _is_verified_setuptools_egg(repo_path / root)
        )
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
    if not isinstance(tool, dict):
        return ()

    declared: set[str] = set()
    setuptools_scm = tool.get("setuptools_scm")
    if isinstance(setuptools_scm, dict):
        declared.update(
            path
            for key in ("version_file", "write_to")
            if (path := _safe_relative_path(setuptools_scm.get(key))) is not None
        )

    versioningit = tool.get("versioningit")
    versioningit_write = (
        versioningit.get("write") if isinstance(versioningit, dict) else None
    )
    if isinstance(versioningit_write, dict):
        path = _safe_relative_path(versioningit_write.get("file"))
        if path is not None:
            declared.add(path)

    return tuple(sorted(declared))


def _is_allowed_generated(
    path: str,
    environment_roots: tuple[PurePosixPath, ...] = (),
    setuptools_egg_roots: tuple[PurePosixPath, ...] = (),
    declared_generated_paths: tuple[str, ...] = (),
    ignored_paths: frozenset[str] = frozenset(),
    repository_derived_paths: frozenset[str] = frozenset(),
) -> bool:
    pure = PurePosixPath(path)
    if any(_inside_root(pure, root) for root in environment_roots):
        return True
    if any(_inside_root(pure, root) for root in setuptools_egg_roots):
        return True
    if path in declared_generated_paths and path in ignored_paths:
        return True
    if path in repository_derived_paths:
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
    environment_roots: tuple[PurePosixPath, ...] = (),
    setuptools_egg_roots: tuple[PurePosixPath, ...] = (),
    declared_generated_paths: tuple[str, ...] = (),
    repository_derived_paths: frozenset[str] = frozenset(),
) -> str | None:
    pure = PurePosixPath(path)
    for root in environment_roots:
        if _inside_root(pure, root):
            return str(root) + "/"
    for root in setuptools_egg_roots:
        if _inside_root(pure, root):
            return str(root) + "/"
    if path in declared_generated_paths:
        return path
    if path in repository_derived_paths:
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


def _repository_derived_artifact(
    repo_path: Path,
    expected_revision: str,
    path: str,
    tracked_paths: tuple[str, ...],
    ignored_paths: frozenset[str],
) -> RepositoryDerivedArtifact | None:
    target = PurePosixPath(path)
    if (
        path not in ignored_paths
        or target.suffix.lower() not in {".py", ".pyi"}
    ):
        return None
    target_path = repo_path / path
    try:
        if target_path.is_symlink() or not target_path.is_file():
            return None
        target_bytes = target_path.read_bytes()
    except OSError:
        return None

    candidates = (
        source
        for source in tracked_paths
        if source != path
        and PurePosixPath(source).parent == target.parent
        and _is_repository_template(PurePosixPath(source), target)
    )
    for source in candidates:
        blob = _git_bytes(repo_path, "show", f"{expected_revision}:{source}")
        if blob.returncode != 0 or blob.stdout != target_bytes:
            continue
        return RepositoryDerivedArtifact(
            path=path,
            source_path=source,
            sha256=hashlib.sha256(target_bytes).hexdigest(),
        )
    return None


def _is_repository_template(source: PurePosixPath, target: PurePosixPath) -> bool:
    if source.parent != target.parent:
        return False
    if (
        source.stem == target.stem
        and source.suffix.lower() not in IMPORTABLE_SUFFIXES
    ):
        return True
    names = {
        f"{target.name}.{marker}"
        for marker in REPOSITORY_TEMPLATE_MARKERS
    }
    names.update(
        f"{target.stem}.{marker}{target.suffix}"
        for marker in REPOSITORY_TEMPLATE_MARKERS
    )
    return source.name in names


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
    tracked_process = _git(repo_path, "ls-files", "-z")
    tracked_paths = _nul_paths(tracked_process.stdout)
    environment_roots = _environment_roots(repo_path, untracked)
    setuptools_egg_roots = _setuptools_egg_roots(repo_path, untracked)
    declared_generated_paths = _declared_generated_paths(repo_path)
    if (
        untracked_process.returncode != 0
        or ignored_process.returncode != 0
        or tracked_process.returncode != 0
    ):
        violations.append(
            IntegrityViolation(
                "git_error",
                None,
                "repository file inventory: "
                f"{untracked_process.stderr.strip()} "
                f"{ignored_process.stderr.strip()} "
                f"{tracked_process.stderr.strip()}",
            )
        )
    repository_derived_artifacts = tuple(
        artifact
        for path in untracked
        if (artifact := _repository_derived_artifact(
            repo_path,
            expected_revision,
            path,
            tracked_paths,
            ignored_paths,
        ))
        is not None
    )
    repository_derived_paths = frozenset(
        artifact.path for artifact in repository_derived_artifacts
    )
    untracked_violations = {
        path: violation
        for path in untracked
        if not _is_allowed_generated(
            path,
            environment_roots,
            setuptools_egg_roots,
            declared_generated_paths,
            ignored_paths,
            repository_derived_paths,
        )
        for violation in [_untracked_violation(repo_path, path)]
        if violation is not None
    }
    allowed = tuple(
        sorted(
            {
                _generated_root(
                    path,
                    environment_roots,
                    setuptools_egg_roots,
                    declared_generated_paths,
                    repository_derived_paths,
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
        repository_derived_artifacts=repository_derived_artifacts,
        disallowed_untracked_paths=disallowed,
        violations=tuple(violations),
    )
