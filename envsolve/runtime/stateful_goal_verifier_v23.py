from __future__ import annotations

from typing import Any

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.runtime.goal_verifier import ExecutableGoalContractVerifier
from envsolve.runtime.integrity import python_import_alias_audit_command
from envsolve.solver import DeploymentCandidate
from envsolve.verification import RootObligationFindingAdapter


def python_same_environment_alias_audit_command(project_root: str) -> str:
    """Run the shared audit through the same Python resolution as the goal."""
    isolated = python_import_alias_audit_command(project_root)
    prefix = "command python -I "
    if not isolated.startswith(prefix):
        raise RuntimeError("Shared import-alias audit command changed unexpectedly")
    return "python " + isolated[len(prefix) :]


class StatefulExecutableGoalVerifierV23(ExecutableGoalContractVerifier):
    """V2.3 verifier with aligned shell observation and optional compaction."""

    check_profile = "executable-goal-contract-v3.3"

    def __init__(
        self,
        contract: ExecutableGoalContract,
        *,
        compact_findings: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(contract, **kwargs)
        if compact_findings:
            self.finding_adapter = RootObligationFindingAdapter()

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
        isolated_audit = python_import_alias_audit_command(
            handle.container_workdir
        )
        if command.count(isolated_audit) != 1:
            raise RuntimeError("V2.3 could not locate the shared audit boundary")
        return (
            command.replace(
                isolated_audit,
                python_same_environment_alias_audit_command(
                    handle.container_workdir
                ),
                1,
            ),
            completion_marker,
            report_begin,
        )
