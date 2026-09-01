from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
from typing import Any

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.goal_verifier import ExecutableGoalContractVerifier
from envsolve.runtime.integrity import marked_json_payload
from envsolve.solver import (
    CandidateValidation,
    DeploymentCandidate,
    ExecutableVerification,
)
from envsolve_harness.boundary_v2 import NonInterferingExecutableGoalVerifier
from envsolve_harness.boundary_v3 import (
    MANAGED_DEPENDENCY_MARKER,
    adjudicate_managed_dependencies,
)
from envsolve_harness.boundary_v4 import adjudicate_repository_native_artifacts
from envsolve_harness.boundary_v5 import (
    BoundaryV5MinimalBExecutableGoalVerifier,
    BoundaryV5OpenCandidateProgramValidator,
    BoundaryV5RepositoryIntegrityReport,
    adjudicate_repository_tracked_copies,
    install_boundary_v5_local_distribution_audit,
)
from envsolve_harness.integrity.repository import RepositoryIntegrityReport


OPEN_PROGRAM_POLICY = "open-candidate-program-v6"
REPOSITORY_POLICY = "open-operation-postepisode-provenance-v1"


def install_boundary_v6_local_distribution_audit() -> None:
    install_boundary_v5_local_distribution_audit()


@dataclass(frozen=True)
class ReviewRequiredImportArtifact:
    path: str
    size_bytes: int
    sha256: str
    disposition: str = "postepisode-executable-source-review"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BoundaryV6RepositoryIntegrityReport:
    base: BoundaryV5RepositoryIntegrityReport
    review_required_artifacts: tuple[ReviewRequiredImportArtifact, ...]
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
                "review_required_artifacts": [
                    artifact.to_dict()
                    for artifact in self.review_required_artifacts[:256]
                ],
                "review_required_artifact_count": len(
                    self.review_required_artifacts
                ),
                "review_required_artifacts_truncated": (
                    len(self.review_required_artifacts) > 256
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


def adjudicate_open_import_artifacts(
    repo_path: Path,
    base: BoundaryV5RepositoryIntegrityReport,
) -> BoundaryV6RepositoryIntegrityReport:
    """Defer nonempty import artifacts to blinded post-episode provenance review."""

    review_required: list[ReviewRequiredImportArtifact] = []
    remaining = []
    for violation in base.remaining_violations:
        if violation.kind != "untracked_import_artifact" or violation.path is None:
            remaining.append(violation)
            continue
        artifact = repo_path / violation.path
        try:
            if artifact.is_symlink() or not artifact.is_file():
                remaining.append(violation)
                continue
            data = artifact.read_bytes()
        except OSError:
            remaining.append(violation)
            continue
        if not data:
            remaining.append(violation)
            continue
        review_required.append(
            ReviewRequiredImportArtifact(
                path=violation.path,
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
            )
        )
    return BoundaryV6RepositoryIntegrityReport(
        base=base,
        review_required_artifacts=tuple(
            sorted(review_required, key=lambda item: item.path)
        ),
        remaining_violations=tuple(remaining),
    )


class BoundaryV6OpenCandidateProgramValidator(
    BoundaryV5OpenCandidateProgramValidator
):
    policy_id = OPEN_PROGRAM_POLICY
    allow_direct_import_artifacts = True
    prompt_contract = """\
Return one complete, self-contained Bash program that will be inserted inline into
the controlling Bash process from the project root in a fresh container. No
harness-specific project-root environment variable is defined; use `$PWD` when an
absolute project path is needed. Normal Bash composition and control flow are
allowed, but do not terminate or replace the controlling shell with `exit`,
`return`, or `exec`.

The operation space is open. You may materialize nonempty repository-local build
outputs or local deployment configuration when the repository's own build,
installation, or configuration intent requires them. Do not edit tracked repository
files, suppress the terminal verifier, delete evaluator-owned workspace artifacts,
or create import aliases by symlinking repository paths into Python package search
directories. The program must leave the selected Python environment active, and it
must return the controlling shell to its starting project root before it finishes.

Safety and correctness are decided by isolated execution, executable
postconditions, tracked-state integrity, and post-episode provenance review of new
import artifacts. Empty files and empty namespace shims are not valid deployment
artifacts.
""".strip()

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


class BoundaryV6MinimalBExecutableGoalVerifier(
    BoundaryV5MinimalBExecutableGoalVerifier
):
    check_profile = "minimal-b-executable-goal-contract-boundary-v6"

    def _effect_audit(  # type: ignore[no-untyped-def]
        self,
        handle: DockerEnvironmentHandle,
        result: Any,
    ):
        if self.effect_auditor is None:
            return None, None
        provenance = marked_json_payload(result.stdout, MANAGED_DEPENDENCY_MARKER)
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
            tracked = adjudicate_repository_tracked_copies(
                handle.worktree,
                native,
            )
            report = adjudicate_open_import_artifacts(handle.worktree, tracked)
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


class BoundaryV6OfficialAlignedExecutableGoalVerifier(
    BoundaryV6MinimalBExecutableGoalVerifier
):
    check_profile = "official-aligned-executable-goal-boundary-v6-v1"

    def _command(
        self,
        candidate: DeploymentCandidate,
        handle: DockerEnvironmentHandle,
        nonce: str,
    ) -> tuple[str, str, str]:
        return NonInterferingExecutableGoalVerifier._command(
            self,
            candidate,
            handle,
            nonce,
        )

    def verify(
        self,
        candidate: DeploymentCandidate,
        environment: Any,
    ) -> ExecutableVerification:
        return ExecutableGoalContractVerifier.verify(
            self,
            candidate,
            environment,
        )
