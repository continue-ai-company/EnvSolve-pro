from __future__ import annotations

from dataclasses import replace
from pathlib import PurePosixPath
import shlex

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.goal_verifier import ExecutableGoalContractVerifier
from envsolve.runtime.stateful_integrity_v2 import (
    python_source_provenance_audit_command,
)
from envsolve.solver import (
    DeploymentCandidate,
    ExecutableVerification,
    HypothesisEvidence,
    ObservationEvidence,
    ProvisionedEnvironment,
)


_CANDIDATE_COMPLETION_PREFIX = "ENVSOLVE_GOAL_CANDIDATE_COMPLETED_V1="
_OUTER_WORKSPACE_VIOLATION_PREFIX = (
    "ENVSOLVE_GOAL_OUTER_WORKSPACE_VIOLATION_V1="
)
_PROTECTED_ENVIRONMENT_VIOLATION_PREFIX = (
    "ENVSOLVE_GOAL_PROTECTED_ENVIRONMENT_VIOLATION_V1="
)
_DIVERGENT_SOURCE_REASON = (
    "external import search root contributes divergent project source"
)


class StatefulExecutableGoalVerifierV2(ExecutableGoalContractVerifier):
    """V2 goal verifier isolated from frozen shared verifier implementations."""

    check_profile = "executable-goal-contract-v3"

    def _command(
        self,
        candidate: DeploymentCandidate,
        handle: DockerEnvironmentHandle,
        nonce: str,
    ) -> tuple[str, str, str]:
        completion_marker = f"{_CANDIDATE_COMPLETION_PREFIX}{nonce}"
        report_begin = f"ENVSOLVE_GOAL_REPORT_BEGIN_V1={nonce}"
        report_end = f"ENVSOLVE_GOAL_REPORT_END_V1={nonce}"
        report_path = f"/tmp/envsolve-goal-report-{nonce}.json"
        project_path = PurePosixPath(handle.container_workdir)
        outer_workspace = str(project_path.parent)
        protected_prefixes = " ".join(
            shlex.quote(prefix)
            for prefix in self.contract.protected_environment_prefixes
        )
        lines = [
            "set -e",
            (
                'trap \'rc=$?; printf "ENVSOLVE_GOAL_CANDIDATE_FAILED_V1=%s\\n" '
                '"$rc" >&2; exit "$rc"\' ERR'
            ),
            candidate.script.rstrip(),
            "set +u",
            "set +x",
            "set +o pipefail",
            "IFS=$' \\t\\n'",
            "trap - EXIT ERR RETURN DEBUG",
            "set -e",
            f"cd -- {shlex.quote(handle.container_workdir)}",
            (
                f"for ENVSOLVE_PROTECTED_PREFIX in {protected_prefixes}; do "
                "while IFS='=' read -r ENVSOLVE_ENV_NAME _; do "
                'case "$ENVSOLVE_ENV_NAME" in '
                '"$ENVSOLVE_PROTECTED_PREFIX"*) '
                f"printf '{_PROTECTED_ENVIRONMENT_VIOLATION_PREFIX}%s\\n' "
                '"$ENVSOLVE_ENV_NAME" >&2; exit 254 ;; '
                "esac; "
                "done < <(/usr/bin/env); "
                "done"
                if protected_prefixes
                else ":"
            ),
            f"ENVSOLVE_OUTER_WORKSPACE={shlex.quote(outer_workspace)}",
            (
                'if [ -d "$ENVSOLVE_OUTER_WORKSPACE" ]; then '
                "ENVSOLVE_UNEXPECTED_OUTER_PATH=$("
                '/usr/bin/find "$ENVSOLVE_OUTER_WORKSPACE" '
                "-mindepth 1 -maxdepth 1 "
                f"! -path {shlex.quote(handle.container_workdir)} "
                "-print -quit"
                "); "
                'if [ -n "$ENVSOLVE_UNEXPECTED_OUTER_PATH" ]; then '
                f"printf '{_OUTER_WORKSPACE_VIOLATION_PREFIX}%s\\n' "
                '"$ENVSOLVE_UNEXPECTED_OUTER_PATH" >&2; '
                "exit 253; "
                "fi; "
                "fi"
            ),
            f"printf '%s\\n' {shlex.quote(completion_marker)}",
            python_source_provenance_audit_command(handle.container_workdir),
            "trap - ERR",
            f"export ENVSOLVE_PROJECT_ROOT={shlex.quote(handle.container_workdir)}",
            f"export ENVSOLVE_GOAL_REPORT={shlex.quote(report_path)}",
            'rm -f "$ENVSOLVE_GOAL_REPORT"',
            "set +e",
            "(",
            "set -e",
            self.contract.program.rstrip(),
            ")",
            "ENVSOLVE_GOAL_EXIT_CODE=$?",
            "set -e",
            f"printf '%s\\n' {shlex.quote(report_begin)}",
            'if [ -f "$ENVSOLVE_GOAL_REPORT" ]; then cat "$ENVSOLVE_GOAL_REPORT"; fi',
            "printf '\\n%s\\n' " + shlex.quote(report_end),
            'rm -f "$ENVSOLVE_GOAL_REPORT"',
            'exit "$ENVSOLVE_GOAL_EXIT_CODE"',
        ]
        return "\n".join(lines), completion_marker, report_begin + "\n"

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
                and item.get("reason") == _DIVERGENT_SOURCE_REASON
                for item in violations
            )
        ):
            return result
        return replace(
            result,
            summary="Candidate mixed the project namespace with an external source",
            hypotheses=(
                HypothesisEvidence(
                    hypothesis_id=(
                        "hypothesis-goal-contract-project-namespace-provenance"
                    ),
                    statement=(
                        "Project import namespaces must not be completed by "
                        "divergent external source"
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
                        "kind": "project-namespace-provenance",
                        "violations": violations,
                    },
                    1.0,
                ),
            ),
        )


class StatefulExecutableGoalVerifierV21(StatefulExecutableGoalVerifierV2):
    """Observe the base goal before applying candidate-attribution checks."""

    check_profile = "executable-goal-contract-v3.1"

    def _command(
        self,
        candidate: DeploymentCandidate,
        handle: DockerEnvironmentHandle,
        nonce: str,
    ) -> tuple[str, str, str]:
        if candidate.metadata.get("execution_role") == "initial-observation":
            return ExecutableGoalContractVerifier._command(
                self,
                candidate,
                handle,
                nonce,
            )
        return super()._command(candidate, handle, nonce)
