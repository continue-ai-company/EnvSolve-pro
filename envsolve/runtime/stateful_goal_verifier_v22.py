from __future__ import annotations

from dataclasses import replace

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.stateful_goal_verifier_v2 import (
    StatefulExecutableGoalVerifierV21,
)
from envsolve.runtime.stateful_integrity_v2 import (
    python_source_provenance_audit_command,
)
from envsolve.runtime.stateful_integrity_v22 import (
    MODULE_IDENTITY_VIOLATION_REASON,
    python_module_identity_audit_command,
)
from envsolve.solver import (
    DeploymentCandidate,
    ExecutableVerification,
    HypothesisEvidence,
    ObservationEvidence,
    ProvisionedEnvironment,
)


class StatefulExecutableGoalVerifierV22(StatefulExecutableGoalVerifierV21):
    """Add module-identity provenance without changing the frozen V2.1 verifier."""

    check_profile = "executable-goal-contract-v3.2"

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
        if candidate.metadata.get("execution_role") == "initial-observation":
            return command, completion_marker, report_begin
        old_audit = python_source_provenance_audit_command(
            handle.container_workdir
        )
        if command.count(old_audit) != 1:
            raise RuntimeError("V2.2 could not locate the V2 provenance boundary")
        return (
            command.replace(
                old_audit,
                python_module_identity_audit_command(
                    handle.container_workdir
                ),
                1,
            ),
            completion_marker,
            report_begin,
        )

    def verify(
        self,
        candidate: DeploymentCandidate,
        environment: ProvisionedEnvironment,
    ) -> ExecutableVerification:
        result = super().verify(candidate, environment)
        audit = result.details.get("import_alias_audit")
        violations = audit.get("violations") if isinstance(audit, dict) else None
        if not (
            isinstance(violations, list)
            and any(
                isinstance(item, dict)
                and item.get("reason") == MODULE_IDENTITY_VIOLATION_REASON
                for item in violations
            )
        ):
            return result
        return replace(
            result,
            summary="Candidate assigned project source to an undeclared module identity",
            hypotheses=(
                HypothesisEvidence(
                    hypothesis_id=(
                        "hypothesis-goal-contract-project-module-identity"
                    ),
                    statement=(
                        "Project source must retain its declared import identity"
                    ),
                    value={"import_alias_audit": audit},
                    confidence=1.0,
                ),
            ),
            observations=(
                ObservationEvidence(
                    "candidate-integrity-observation",
                    {
                        "integrity_valid": False,
                        "kind": "project-module-identity",
                        "violations": violations,
                    },
                    1.0,
                ),
            ),
        )
