from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.goal_verifier import ExecutableGoalContractVerifier
from envsolve.runtime.integrity import marked_json_payload
from envsolve.solver import CandidateValidation, DeploymentCandidate
from envsolve_harness.boundary_v3 import (
    MANAGED_DEPENDENCY_MARKER,
    adjudicate_managed_dependencies,
    boundary_v3_novel_local_distribution_violations,
)
from envsolve_harness.boundary_v4 import (
    BoundaryV4MinimalBExecutableGoalVerifier,
    BoundaryV4OpenCandidateProgramValidator,
    BoundaryV4RepositoryIntegrityReport,
    adjudicate_repository_native_artifacts,
    boundary_v4_local_distribution_audit,
)
from envsolve_harness.codex import minimal_b_mcp
from envsolve_harness.integrity.repository import RepositoryIntegrityReport


OPEN_PROGRAM_POLICY = "open-candidate-program-v5"
REPOSITORY_POLICY = "submitted-state-plus-build-provenance-v9"
TRACKED_COPY_POLICY = "exact-committed-source-copy-with-path-preservation-v1"

_TRACKED_COPY_SUFFIXES = frozenset({".py", ".pyi"})

_V4_SOURCE_MAP_INITIALIZATION = "native_provider_sources = {}\n"
_V5_SOURCE_MAP_INITIALIZATION = """\
native_provider_sources = {}
tracked_python_source_bytes = {}
"""
_V4_SOURCE_READ = '''\
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
'''
_V5_SOURCE_READ = '''\
        source_path = project_root / relative_path
        source_suffix = source_path.suffix.lower()
        if source_suffix not in native_source_suffixes | {".py", ".pyi"}:
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
        if source_suffix in {".py", ".pyi"}:
            tracked_python_source_bytes[relative_path] = source.stdout
            continue
        for pattern in native_provider_patterns:
'''
_V4_NATIVE_PROVIDERS_OUTPUT = '''\
repository_native_providers = {
    module: sorted(paths)
    for module, paths in sorted(native_provider_sources.items())
}

def repository_native_artifact(path, root):
'''
_V5_TRACKED_COPY_AUDIT = '''\
repository_native_providers = {
    module: sorted(paths)
    for module, paths in sorted(native_provider_sources.items())
}

def repository_tracked_copy(path, root):
    if path.suffix.lower() not in {".py", ".pyi"}:
        return None
    try:
        if path.is_symlink() or not path.is_file():
            return None
        artifact_bytes = path.read_bytes()
    except OSError:
        return None
    relative_parts = path.relative_to(root).parts
    for source_path, source_bytes in sorted(tracked_python_source_bytes.items()):
        source_parts = Path(source_path).parts
        if len(relative_parts) < len(source_parts):
            continue
        if relative_parts[-len(source_parts):] != source_parts:
            continue
        if artifact_bytes != source_bytes:
            continue
        return {
            "audit_kind": "repository-tracked-source-copy",
            "site_root": str(root.resolve()),
            "relative_path": str(path.relative_to(root)),
            "source_path": source_path,
            "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
            "derivation": "exact-committed-source-copy-with-path-preservation",
        }
    return None

def repository_native_artifact(path, root):
'''
_V4_IMPORT_ARTIFACT_ADJUDICATION = '''\
        native_artifact = repository_native_artifact(path, root)
        if native_artifact is not None:
            repository_native_artifacts.append(native_artifact)
            continue
        unowned_import_artifacts.append(
'''
_V5_IMPORT_ARTIFACT_ADJUDICATION = '''\
        tracked_copy = repository_tracked_copy(path, root)
        if tracked_copy is not None:
            repository_tracked_copies.append(tracked_copy)
            continue
        native_artifact = repository_native_artifact(path, root)
        if native_artifact is not None:
            repository_native_artifacts.append(native_artifact)
            continue
        unowned_import_artifacts.append(
'''
_V4_FINDING_INITIALIZATION = '''\
repository_native_artifacts = []
unowned_import_artifacts = []
'''
_V5_FINDING_INITIALIZATION = '''\
repository_native_artifacts = []
repository_tracked_copies = []
unowned_import_artifacts = []
'''
_V4_OUTPUT_FIELD = '''\
            "repository_native_artifacts": repository_native_artifacts,
            "repository_native_providers": repository_native_providers,
'''
_V5_OUTPUT_FIELD = '''\
            "repository_native_artifacts": repository_native_artifacts,
            "repository_native_providers": repository_native_providers,
            "repository_tracked_copies": repository_tracked_copies,
'''
_V4_DISTRIBUTION_SCAN = "distributions = list(importlib.metadata.distributions())"
_V5_DISTRIBUTION_SCAN = '''\
configured_import_roots = {
    value
    for value in os.environ.get("PYTHONPATH", "").split(os.pathsep)
    if value and Path(value).is_dir()
}
distributions = []
seen_distributions = set()
distribution_search_paths = [None, *sorted(configured_import_roots)]
for distribution_search_path in distribution_search_paths:
    candidates = (
        importlib.metadata.distributions()
        if distribution_search_path is None
        else importlib.metadata.distributions(path=[distribution_search_path])
    )
    for distribution in candidates:
        try:
            distribution_key = (
                str(Path(distribution.locate_file("")).resolve()),
                distribution.metadata.get("Name", "unknown"),
                distribution.version,
            )
        except (OSError, RuntimeError):
            distribution_key = (
                distribution_search_path,
                distribution.metadata.get("Name", "unknown"),
                distribution.version,
            )
        if distribution_key in seen_distributions:
            continue
        seen_distributions.add(distribution_key)
        distributions.append(distribution)
'''


def boundary_v5_local_distribution_audit() -> str:
    """Audit import roots with committed-source build provenance."""
    source = boundary_v4_local_distribution_audit()
    replacements = (
        (_V4_DISTRIBUTION_SCAN, _V5_DISTRIBUTION_SCAN),
        (_V4_SOURCE_MAP_INITIALIZATION, _V5_SOURCE_MAP_INITIALIZATION),
        (_V4_SOURCE_READ, _V5_SOURCE_READ),
        (_V4_NATIVE_PROVIDERS_OUTPUT, _V5_TRACKED_COPY_AUDIT),
        (_V4_FINDING_INITIALIZATION, _V5_FINDING_INITIALIZATION),
        (_V4_IMPORT_ARTIFACT_ADJUDICATION, _V5_IMPORT_ARTIFACT_ADJUDICATION),
        (_V4_OUTPUT_FIELD, _V5_OUTPUT_FIELD),
    )
    for old, new in replacements:
        if source.count(old) != 1:
            raise RuntimeError("cannot install boundary-v5 build-provenance audit")
        source = source.replace(old, new, 1)
    source = source.removeprefix("\\\n").replace("\n\\\n", "\n")
    if any(line == "\\" for line in source.splitlines()):
        raise RuntimeError("boundary-v5 audit contains an invalid line continuation")
    return source


def boundary_v5_novel_local_distribution_violations(
    baseline: dict[str, Any],
    post: dict[str, Any],
) -> list[dict[str, Any]]:
    return boundary_v3_novel_local_distribution_violations(baseline, post)


def install_boundary_v5_local_distribution_audit() -> None:
    minimal_b_mcp._LOCAL_DISTRIBUTION_AUDIT = (
        boundary_v5_local_distribution_audit()
    )
    minimal_b_mcp._novel_local_distribution_violations = (
        boundary_v5_novel_local_distribution_violations
    )


def _tracked_python_sources(
    repo_path: Path,
    expected_revision: str,
) -> dict[str, bytes]:
    inventory = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "-z", expected_revision],
        cwd=repo_path,
        capture_output=True,
        check=False,
    )
    if inventory.returncode != 0:
        return {}
    sources: dict[str, bytes] = {}
    for encoded in inventory.stdout.split(b"\0"):
        if not encoded:
            continue
        path = encoded.decode("utf-8", errors="surrogateescape")
        if PurePosixPath(path).suffix.lower() not in _TRACKED_COPY_SUFFIXES:
            continue
        blob = subprocess.run(
            ["git", "show", f"{expected_revision}:{path}"],
            cwd=repo_path,
            capture_output=True,
            check=False,
        )
        if blob.returncode == 0:
            sources[path] = blob.stdout
    return sources


@dataclass(frozen=True)
class RepositoryTrackedCopyArtifact:
    path: str
    source_path: str
    sha256: str
    derivation: str = "exact-committed-source-copy-with-path-preservation"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _repository_tracked_copy(
    repo_path: Path,
    path: str,
    sources: dict[str, bytes],
) -> RepositoryTrackedCopyArtifact | None:
    target = PurePosixPath(path)
    if target.suffix.lower() not in _TRACKED_COPY_SUFFIXES:
        return None
    artifact = repo_path / path
    try:
        if artifact.is_symlink() or not artifact.is_file():
            return None
        data = artifact.read_bytes()
    except OSError:
        return None
    for source_path, source_bytes in sorted(sources.items()):
        source = PurePosixPath(source_path)
        if len(target.parts) < len(source.parts):
            continue
        if target.parts[-len(source.parts) :] != source.parts:
            continue
        if data != source_bytes:
            continue
        return RepositoryTrackedCopyArtifact(
            path=path,
            source_path=source_path,
            sha256=hashlib.sha256(data).hexdigest(),
        )
    return None


@dataclass(frozen=True)
class BoundaryV5RepositoryIntegrityReport:
    base: BoundaryV4RepositoryIntegrityReport
    tracked_copy_policy: str
    accepted_tracked_copies: tuple[RepositoryTrackedCopyArtifact, ...]
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
                "tracked_copy_policy": self.tracked_copy_policy,
                "accepted_tracked_copies": [
                    artifact.to_dict()
                    for artifact in self.accepted_tracked_copies[:256]
                ],
                "accepted_tracked_copy_count": len(self.accepted_tracked_copies),
                "accepted_tracked_copies_truncated": (
                    len(self.accepted_tracked_copies) > 256
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


def adjudicate_repository_tracked_copies(
    repo_path: Path,
    base: BoundaryV4RepositoryIntegrityReport,
) -> BoundaryV5RepositoryIntegrityReport:
    sources = _tracked_python_sources(
        repo_path,
        base.base.base.expected_revision,
    )
    accepted: list[RepositoryTrackedCopyArtifact] = []
    remaining = []
    for violation in base.remaining_violations:
        artifact = (
            _repository_tracked_copy(repo_path, violation.path, sources)
            if violation.kind == "untracked_import_artifact"
            and violation.path is not None
            else None
        )
        if artifact is None:
            remaining.append(violation)
        else:
            accepted.append(artifact)
    return BoundaryV5RepositoryIntegrityReport(
        base=base,
        tracked_copy_policy=TRACKED_COPY_POLICY,
        accepted_tracked_copies=tuple(
            sorted(accepted, key=lambda item: item.path)
        ),
        remaining_violations=tuple(remaining),
    )


class BoundaryV5OpenCandidateProgramValidator(
    BoundaryV4OpenCandidateProgramValidator
):
    policy_id = OPEN_PROGRAM_POLICY
    prompt_contract = BoundaryV4OpenCandidateProgramValidator.prompt_contract

    def validate(self, candidate: DeploymentCandidate) -> CandidateValidation:
        result = super().validate(candidate)
        return CandidateValidation(
            result.accepted,
            self.policy_id,
            normalized_script=result.normalized_script,
            reason=result.reason,
            details={
                **result.details,
                **({"interface": self.policy_id} if result.accepted else {}),
            },
        )


class BoundaryV5MinimalBExecutableGoalVerifier(
    BoundaryV4MinimalBExecutableGoalVerifier
):
    check_profile = "minimal-b-executable-goal-contract-boundary-v5"

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
            native = adjudicate_repository_native_artifacts(
                handle.worktree,
                managed,
            )
            report = adjudicate_repository_tracked_copies(
                handle.worktree,
                native,
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
