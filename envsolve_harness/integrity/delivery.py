from __future__ import annotations

from typing import Any
import re
import shlex

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.solver import (
    DeploymentCandidate,
    ExecutableVerification,
    FeedbackChannel,
    HypothesisEvidence,
)
from envsolve_harness.integrity.minimal import MinimalIntegrityGoalVerifier


_WORKING_DIRECTORY_VIOLATION_PREFIX = (
    "ENVSOLVE_GOAL_WORKING_DIRECTORY_VIOLATION_V1="
)
_WORKING_DIRECTORY_VIOLATION = re.compile(
    rf"^{_WORKING_DIRECTORY_VIOLATION_PREFIX}(?P<path>[^\r\n]+)$",
    re.MULTILINE,
)


class FinalWorkingDirectoryPostconditionMixin:
    """Require a sourced candidate to restore its initial project directory."""

    def _command(
        self,
        candidate: DeploymentCandidate,
        handle: DockerEnvironmentHandle,
        nonce: str,
    ) -> tuple[str, str, str]:
        command, completion_marker, report_begin = super()._command(  # type: ignore[misc]
            candidate,
            handle,
            nonce,
        )
        completion_line = f"printf '%s\\n' {shlex.quote(completion_marker)}"
        if command.count(completion_line) != 1:
            raise RuntimeError("cannot instrument final working-directory postcondition")
        check = "\n".join(
            (
                (
                    "ENVSOLVE_EXPECTED_PROJECT_ROOT=$(cd -- "
                    f"{shlex.quote(handle.container_workdir)} && pwd -P)"
                ),
                "ENVSOLVE_ACTUAL_PROJECT_ROOT=$(pwd -P)",
                (
                    'if [ "$ENVSOLVE_ACTUAL_PROJECT_ROOT" != '
                    '"$ENVSOLVE_EXPECTED_PROJECT_ROOT" ]; then '
                    f"printf '{_WORKING_DIRECTORY_VIOLATION_PREFIX}%s\\n' "
                    '"$ENVSOLVE_ACTUAL_PROJECT_ROOT" >&2; exit 252; fi'
                ),
            )
        )
        return (
            command.replace(completion_line, f"{check}\n{completion_line}", 1),
            completion_marker,
            report_begin,
        )

    def verify(
        self,
        candidate: DeploymentCandidate,
        environment: Any,
    ) -> ExecutableVerification:
        outcome = super().verify(candidate, environment)  # type: ignore[misc]
        violation = _WORKING_DIRECTORY_VIOLATION.search(outcome.bootstrap.stderr)
        if (
            violation is None
            or outcome.summary
            != "Candidate did not return control to the executable goal"
        ):
            return outcome
        handle = environment.handle
        if not isinstance(handle, DockerEnvironmentHandle):
            return outcome
        path = violation.group("path")
        detail = {
            "actual_path": path,
            "expected_project_path": handle.container_workdir,
        }
        return ExecutableVerification(
            verifier="envsolve-delivery-integrity-verifier",
            check_profile=self.check_profile,
            channel=FeedbackChannel.INTERNAL_EXECUTION,
            passed=False,
            bootstrap=outcome.bootstrap,
            summary="Candidate did not return to the project root",
            hypotheses=(
                HypothesisEvidence(
                    hypothesis_id="hypothesis-goal-contract-working-directory",
                    statement=(
                        "The candidate must leave the controlling shell in the "
                        "project root for subsequent deployment actions"
                    ),
                    value=detail,
                    confidence=1.0,
                ),
            ),
            details={
                **outcome.details,
                "working_directory_violation": detail,
            },
        )


class DeliveryIntegrityGoalVerifier(
    FinalWorkingDirectoryPostconditionMixin,
    MinimalIntegrityGoalVerifier,
):
    """Minimal evaluator integrity plus target-delivery shell-state integrity."""

    check_profile = "executable-goal-delivery-integrity-v1"
