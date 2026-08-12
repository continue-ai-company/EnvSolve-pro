from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.goal_verifier import ExecutableGoalContractVerifier
from envsolve.runtime.integrity import marked_json_payload
from envsolve.solver import CandidateValidation, DeploymentCandidate
from envsolve_harness.boundary_v3 import (
    MANAGED_DEPENDENCY_MARKER,
    BoundaryV3MinimalBExecutableGoalVerifier,
    BoundaryV3OpenCandidateProgramValidator,
    BoundaryV3RepositoryIntegrityReport,
    adjudicate_managed_dependencies,
    boundary_v3_local_distribution_audit,
    boundary_v3_novel_local_distribution_violations,
)
from envsolve_harness.codex import minimal_b_mcp
from envsolve_harness.integrity.repository import RepositoryIntegrityReport


OPEN_PROGRAM_POLICY = "open-candidate-program-v4"
REPOSITORY_POLICY = "submitted-state-plus-native-build-provenance-v8"
NATIVE_BUILD_POLICY = "tracked-native-provider-v1"

_NATIVE_SOURCE_SUFFIXES = frozenset(
    {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".m", ".mm"}
)
_COMPILED_EXTENSION_SUFFIXES = frozenset({".pyd", ".so"})
_NATIVE_PROVIDER_PATTERNS = (
    re.compile(rb"\bPyInit_([A-Za-z_][A-Za-z0-9_]*)\s*\("),
    re.compile(rb"\bPYBIND11_MODULE\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,"),
    re.compile(rb"\bNB_MODULE\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,"),
)
_NATIVE_BINARY_MAGICS = (
    b"\x7fELF",
    b"MZ",
    b"\xca\xfe\xba\xbe",
    b"\xcf\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
)

_V3_AUDIT_IMPORTS = """\
import hashlib
import importlib.metadata
import json
"""
_V4_AUDIT_IMPORTS = """\
import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import tempfile
"""
_V4_NATIVE_PROVIDER_AUDIT = r'''native_source_suffixes = {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".m", ".mm"
}
native_provider_patterns = (
    re.compile(rb"\bPyInit_([A-Za-z_][A-Za-z0-9_]*)\s*\("),
    re.compile(rb"\bPYBIND11_MODULE\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,"),
    re.compile(rb"\bNB_MODULE\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,"),
)
native_provider_sources = {}
trusted_git_config = None
try:
    system_git = next(
        (value for value in ("/usr/bin/git", "/bin/git") if Path(value).is_file()),
        None,
    )
    if system_git is None:
        raise FileNotFoundError("no trusted system Git executable")
    if "\n" in str(project_root) or "\r" in str(project_root):
        raise ValueError("project path cannot be represented in Git config")
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix="envsolve-git-",
        suffix=".config",
        dir="/tmp",
        delete=False,
    ) as handle:
        handle.write("[safe]\n\tdirectory = " + str(project_root) + "\n")
        trusted_git_config = Path(handle.name)
    git_environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    git_environment.update(
        {
            "GIT_CONFIG_GLOBAL": str(trusted_git_config),
            "GIT_CONFIG_SYSTEM": "/dev/null",
        }
    )
    inventory = subprocess.run(
        [system_git, "ls-files", "-z"],
        cwd=project_root,
        capture_output=True,
        check=False,
        env=git_environment,
    )
    if inventory.returncode != 0:
        raise RuntimeError(inventory.stderr.decode(errors="replace")[-2000:])
    for encoded_path in inventory.stdout.split(b"\0"):
        if not encoded_path:
            continue
        relative_path = encoded_path.decode("utf-8", errors="surrogateescape")
        source_path = project_root / relative_path
        if source_path.suffix.lower() not in native_source_suffixes:
            continue
        source = subprocess.run(
            [system_git, "show", "HEAD:" + relative_path],
            cwd=project_root,
            capture_output=True,
            check=False,
            env=git_environment,
        )
        if source.returncode != 0:
            continue
        for pattern in native_provider_patterns:
            for match in pattern.finditer(source.stdout):
                module = match.group(1).decode("ascii")
                native_provider_sources.setdefault(module, set()).add(relative_path)
finally:
    if trusted_git_config is not None:
        trusted_git_config.unlink(missing_ok=True)

repository_native_providers = {
    module: sorted(paths)
    for module, paths in sorted(native_provider_sources.items())
}

def repository_native_artifact(path, root):
    if path.suffix.lower() not in {".so", ".pyd"}:
        return None
    module = path.name.split(".", 1)[0]
    source_paths = repository_native_providers.get(module)
    if not source_paths:
        return None
    try:
        if path.is_symlink() or not path.is_file():
            return None
        artifact_bytes = path.read_bytes()
    except OSError:
        return None
    valid_magic = artifact_bytes.startswith(
        (b"\x7fELF", b"MZ", b"\xca\xfe\xba\xbe", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf")
    )
    initializer = ("PyInit_" + module).encode("ascii")
    if not valid_magic or initializer not in artifact_bytes:
        return None
    return {
        "audit_kind": "repository-native-build-artifact",
        "site_root": str(root.resolve()),
        "relative_path": str(path.relative_to(root)),
        "module": module,
        "source_paths": source_paths,
        "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
        "derivation": "tracked-native-provider-and-exported-initializer",
    }
'''
_V3_DISTRIBUTION_SCAN = "distributions = list(importlib.metadata.distributions())"
_V4_DISTRIBUTION_SCAN = (
    _V4_NATIVE_PROVIDER_AUDIT + "\n" + _V3_DISTRIBUTION_SCAN
)
_V3_IMPORT_ROOT_SCAN = """\
unowned_import_artifacts = []
for encoded_root in sorted(site_roots):
"""
_V4_IMPORT_ROOT_SCAN = r'''effective_import_roots = set(site_roots)
configured_import_roots = {
    value
    for value in os.environ.get("PYTHONPATH", "").split(os.pathsep)
    if value
}
effective_import_roots.update(configured_import_roots)
standard_library_roots = {
    Path(value).resolve()
    for key in ("stdlib", "platstdlib")
    if (value := sysconfig.get_paths().get(key))
}
resolved_site_roots = {
    Path(value).resolve()
    for value in site_roots
    if Path(value).is_dir()
}
for value in sys.path:
    if not value:
        continue
    candidate_root = Path(value)
    if not candidate_root.is_dir():
        continue
    try:
        resolved_candidate_root = candidate_root.resolve()
    except (OSError, RuntimeError):
        continue
    standard_library_path = any(
        resolved_candidate_root == standard_root
        or resolved_candidate_root.is_relative_to(standard_root)
        for standard_root in standard_library_roots
    )
    if standard_library_path and resolved_candidate_root not in resolved_site_roots:
        continue
    effective_import_roots.add(value)
repository_native_artifacts = []
unowned_import_artifacts = []
for encoded_root in sorted(effective_import_roots):
'''
_V3_IMPORT_ROOT_RESOLUTION = """\
    root = Path(encoded_root)
    if not root.is_dir():
        continue
"""
_V4_IMPORT_ROOT_RESOLUTION = """\
    root = Path(encoded_root)
    if not root.is_dir():
        continue
    try:
        resolved_root = root.resolve()
    except (OSError, RuntimeError):
        continue
    if resolved_root == project_root or resolved_root.is_relative_to(project_root):
        continue
"""
_V3_OWNED_ARTIFACT_SCAN = """\
        if resolved in owned_files:
            continue
        unowned_import_artifacts.append(
"""
_V4_OWNED_ARTIFACT_SCAN = """\
        if resolved in owned_files:
            continue
        native_artifact = repository_native_artifact(path, root)
        if native_artifact is not None:
            repository_native_artifacts.append(native_artifact)
            continue
        unowned_import_artifacts.append(
"""
_V3_OUTPUT_TAIL = """\
            "provided_modules": sorted(provided),
            "trusted_virtualenv_build": trusted_virtualenv_build,
            "virtualenv_runtime_artifacts": virtualenv_runtime_artifacts,
"""
_V4_OUTPUT_TAIL = """\
            "provided_modules": sorted(provided),
            "repository_native_artifacts": repository_native_artifacts,
            "repository_native_providers": repository_native_providers,
            "trusted_virtualenv_build": trusted_virtualenv_build,
            "virtualenv_runtime_artifacts": virtualenv_runtime_artifacts,
"""


def boundary_v4_local_distribution_audit() -> str:
    """Audit all effective import roots with tracked native-provider provenance."""
    source = boundary_v3_local_distribution_audit()
    if _V4_NATIVE_PROVIDER_AUDIT in source:
        return source
    replacements = (
        (_V3_AUDIT_IMPORTS, _V4_AUDIT_IMPORTS),
        (_V3_DISTRIBUTION_SCAN, _V4_DISTRIBUTION_SCAN),
        (_V3_IMPORT_ROOT_SCAN, _V4_IMPORT_ROOT_SCAN),
        (_V3_IMPORT_ROOT_RESOLUTION, _V4_IMPORT_ROOT_RESOLUTION),
        (_V3_OWNED_ARTIFACT_SCAN, _V4_OWNED_ARTIFACT_SCAN),
        (_V3_OUTPUT_TAIL, _V4_OUTPUT_TAIL),
    )
    for old, new in replacements:
        if source.count(old) != 1:
            raise RuntimeError("cannot install boundary-v4 native-build audit")
        source = source.replace(old, new, 1)
    return source


def boundary_v4_novel_local_distribution_violations(
    baseline: dict[str, Any],
    post: dict[str, Any],
) -> list[dict[str, Any]]:
    return boundary_v3_novel_local_distribution_violations(baseline, post)


def install_boundary_v4_local_distribution_audit() -> None:
    minimal_b_mcp._LOCAL_DISTRIBUTION_AUDIT = (
        boundary_v4_local_distribution_audit()
    )
    minimal_b_mcp._novel_local_distribution_violations = (
        boundary_v4_novel_local_distribution_violations
    )


def _native_module_name(path: str) -> str | None:
    pure = PurePosixPath(path)
    if pure.suffix.lower() not in _COMPILED_EXTENSION_SUFFIXES:
        return None
    module = pure.name.split(".", 1)[0]
    return module if module.isidentifier() else None


def _tracked_native_providers(
    repo_path: Path,
    expected_revision: str,
) -> dict[str, tuple[str, ...]]:
    inventory = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "-z", expected_revision],
        cwd=repo_path,
        capture_output=True,
        check=False,
    )
    if inventory.returncode != 0:
        return {}
    providers: dict[str, set[str]] = {}
    for encoded in inventory.stdout.split(b"\0"):
        if not encoded:
            continue
        path = encoded.decode("utf-8", errors="surrogateescape")
        pure = PurePosixPath(path)
        if pure.suffix.lower() not in _NATIVE_SOURCE_SUFFIXES:
            continue
        blob = subprocess.run(
            ["git", "show", f"{expected_revision}:{path}"],
            cwd=repo_path,
            capture_output=True,
            check=False,
        )
        if blob.returncode != 0:
            continue
        for pattern in _NATIVE_PROVIDER_PATTERNS:
            for match in pattern.finditer(blob.stdout):
                module = match.group(1).decode("ascii")
                providers.setdefault(module, set()).add(path)
    return {
        module: tuple(sorted(paths))
        for module, paths in sorted(providers.items())
    }


@dataclass(frozen=True)
class RepositoryNativeArtifact:
    path: str
    module: str
    source_paths: tuple[str, ...]
    sha256: str
    derivation: str = "tracked-native-provider-and-exported-initializer"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["source_paths"] = list(self.source_paths)
        return value


def _repository_native_artifact(
    repo_path: Path,
    path: str,
    providers: dict[str, tuple[str, ...]],
) -> RepositoryNativeArtifact | None:
    module = _native_module_name(path)
    if module is None or module not in providers:
        return None
    artifact = repo_path / path
    try:
        if artifact.is_symlink() or not artifact.is_file():
            return None
        data = artifact.read_bytes()
    except OSError:
        return None
    if not data.startswith(_NATIVE_BINARY_MAGICS):
        return None
    if ("PyInit_" + module).encode("ascii") not in data:
        return None
    return RepositoryNativeArtifact(
        path=path,
        module=module,
        source_paths=providers[module],
        sha256=hashlib.sha256(data).hexdigest(),
    )


@dataclass(frozen=True)
class BoundaryV4RepositoryIntegrityReport:
    base: BoundaryV3RepositoryIntegrityReport
    native_build_policy: str
    native_providers: dict[str, tuple[str, ...]]
    accepted_native_artifacts: tuple[RepositoryNativeArtifact, ...]
    remaining_violations: tuple[Any, ...]

    @property
    def valid(self) -> bool:
        return not self.remaining_violations

    def to_dict(self) -> dict[str, Any]:
        value = self.base.to_dict()
        value.update(
            {
                "policy": REPOSITORY_POLICY,
                "base_policy": value.get("policy"),
                "valid": self.valid,
                "native_build_policy": self.native_build_policy,
                "native_providers": {
                    module: list(paths)
                    for module, paths in self.native_providers.items()
                },
                "accepted_native_artifacts": [
                    artifact.to_dict()
                    for artifact in self.accepted_native_artifacts
                ],
                "accepted_native_artifact_count": len(
                    self.accepted_native_artifacts
                ),
                "disallowed_untracked_paths": [
                    violation.path
                    for violation in self.remaining_violations
                    if getattr(violation, "path", None) is not None
                ],
                "violations": [
                    violation.to_dict()
                    for violation in self.remaining_violations
                ],
            }
        )
        return value


def adjudicate_repository_native_artifacts(
    repo_path: Path,
    base: BoundaryV3RepositoryIntegrityReport,
) -> BoundaryV4RepositoryIntegrityReport:
    providers = _tracked_native_providers(
        repo_path,
        base.base.expected_revision,
    )
    accepted: list[RepositoryNativeArtifact] = []
    remaining = []
    for violation in base.remaining_violations:
        artifact = (
            _repository_native_artifact(repo_path, violation.path, providers)
            if violation.kind == "untracked_import_artifact"
            and violation.path is not None
            else None
        )
        if artifact is None:
            remaining.append(violation)
        else:
            accepted.append(artifact)
    return BoundaryV4RepositoryIntegrityReport(
        base=base,
        native_build_policy=NATIVE_BUILD_POLICY,
        native_providers=providers,
        accepted_native_artifacts=tuple(sorted(accepted, key=lambda item: item.path)),
        remaining_violations=tuple(remaining),
    )


class BoundaryV4OpenCandidateProgramValidator(
    BoundaryV3OpenCandidateProgramValidator
):
    """Keep boundary-v3's operation language under a new measurement policy."""

    policy_id = OPEN_PROGRAM_POLICY
    prompt_contract = BoundaryV3OpenCandidateProgramValidator.prompt_contract

    def validate(self, candidate: DeploymentCandidate) -> CandidateValidation:
        result = super().validate(candidate)
        return CandidateValidation(
            result.accepted,
            self.policy_id,
            normalized_script=result.normalized_script,
            reason=result.reason,
            details={
                **result.details,
                **(
                    {"interface": self.policy_id}
                    if result.accepted
                    else {}
                ),
            },
        )


class BoundaryV4MinimalBExecutableGoalVerifier(
    BoundaryV3MinimalBExecutableGoalVerifier
):
    """Apply location-independent tracked native-build provenance."""

    check_profile = "minimal-b-executable-goal-contract-boundary-v4"

    def _effect_audit(  # type: ignore[no-untyped-def]
        self,
        handle: DockerEnvironmentHandle,
        result: Any,
    ):
        if self.effect_auditor is None:
            return None, None
        provenance = marked_json_payload(
            result.stdout,
            MANAGED_DEPENDENCY_MARKER,
        )
        try:
            raw = self.effect_auditor(handle.worktree)
            if not isinstance(raw, RepositoryIntegrityReport):
                return super()._effect_audit(handle, result)
            managed = adjudicate_managed_dependencies(
                handle.worktree,
                raw,
                provenance,
            )
            report = adjudicate_repository_native_artifacts(
                handle.worktree,
                managed,
            )
        except Exception:
            return super()._effect_audit(handle, result)

        original = self.effect_auditor
        self.effect_auditor = lambda _worktree: report
        try:
            return ExecutableGoalContractVerifier._effect_audit(
                self,
                handle,
                result,
            )
        finally:
            self.effect_auditor = original
