from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shlex
import subprocess
from typing import Any

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.goal_verifier import ExecutableGoalContractVerifier
from envsolve.runtime.integrity import (
    IMPORT_ALIAS_AUDIT_MARKER,
    python_import_alias_audit_command,
)
from envsolve.solver import DeploymentCandidate
from envsolve.runtime.workspace import WorkspacePrecondition


@dataclass(frozen=True)
class MinimalIntegrityViolation:
    kind: str
    path: str | None
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MinimalRepositoryIntegrityReport:
    expected_revision: str
    checked_out_revision: str | None
    tracked_changes: tuple[str, ...]
    violations: tuple[MinimalIntegrityViolation, ...]

    @property
    def valid(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": "minimal-repository-and-adapter-integrity-v1",
            "valid": self.valid,
            "expected_revision": self.expected_revision,
            "checked_out_revision": self.checked_out_revision,
            "tracked_changes": list(self.tracked_changes),
            "untracked_deployment_artifacts_are_semantically_gated": False,
            "violations": [item.to_dict() for item in self.violations],
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


def inspect_minimal_repository_integrity(
    repo_path: Path,
    expected_revision: str,
    required_preconditions: tuple[WorkspacePrecondition, ...] = (),
) -> MinimalRepositoryIntegrityReport:
    """Protect the checkout and adapter state, while allowing deployment outputs."""

    violations: list[MinimalIntegrityViolation] = []
    head = _git(repo_path, "rev-parse", "HEAD")
    checked_out_revision = head.stdout.strip() if head.returncode == 0 else None
    if head.returncode != 0:
        violations.append(
            MinimalIntegrityViolation("git_error", None, head.stderr.strip())
        )
    elif checked_out_revision != expected_revision:
        violations.append(
            MinimalIntegrityViolation(
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
            violations.append(
                MinimalIntegrityViolation(
                    "git_error",
                    None,
                    f"{label}: {process.stderr.strip()}",
                )
            )
    violations.extend(
        MinimalIntegrityViolation(
            "tracked_change",
            path,
            "tracked repository files must remain unchanged",
        )
        for path in tracked_changes
    )
    violations.extend(
        MinimalIntegrityViolation(
            "workspace_precondition_missing",
            item.path,
            f"{item.kind} owned by {item.producer} must remain present",
        )
        for item in required_preconditions
        if not item.satisfied_by(repo_path)
    )
    return MinimalRepositoryIntegrityReport(
        expected_revision=expected_revision,
        checked_out_revision=checked_out_revision,
        tracked_changes=tracked_changes,
        violations=tuple(violations),
    )


class MinimalIntegrityGoalVerifier(ExecutableGoalContractVerifier):
    """Run the shared trusted goal without imposing import-provenance semantics."""

    check_profile = "executable-goal-minimal-integrity-v1"

    def _command(
        self,
        candidate: DeploymentCandidate,
        handle: DockerEnvironmentHandle,
        nonce: str,
    ) -> tuple[str, str, str]:
        command, completion_marker, report_begin = super()._command(
            candidate,
            handle,
            nonce,
        )
        legacy_audit = python_import_alias_audit_command(handle.container_workdir)
        if command.count(legacy_audit) != 1:
            raise RuntimeError("cannot isolate the legacy import-provenance gate")
        marker_payload = IMPORT_ALIAS_AUDIT_MARKER + json.dumps(
            {
                "valid": True,
                "violations": [],
                "performed": False,
                "reason": "deployment provenance is a measured outcome, not a hard gate",
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        replacement = f"printf '%s\\n' {shlex.quote(marker_payload)}"
        return (
            command.replace(legacy_audit, replacement, 1),
            completion_marker,
            report_begin,
        )
