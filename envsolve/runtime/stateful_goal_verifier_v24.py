from __future__ import annotations

from dataclasses import replace
import re
import shlex
from typing import Any

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.runtime.stateful_goal_verifier_v23 import (
    StatefulExecutableGoalVerifierV23,
)
from envsolve.solver import (
    CandidateAssessment,
    DeploymentCandidate,
    ExecutableVerification,
    HypothesisEvidence,
    ObservationEvidence,
    ProvisionedEnvironment,
)
from envsolve.verification import StructuredFindingAdapter


_CANDIDATE_CWD_PREFIX = "ENVSOLVE_CANDIDATE_CWD_V1="
_CANDIDATE_CWD = re.compile(
    rf"^{_CANDIDATE_CWD_PREFIX}(?P<path>[^\r\n]+)$",
    re.MULTILINE,
)


class _TerminalPassFindingAdapter(StructuredFindingAdapter):
    """Do not label a terminal goal pass as an inadmissible repair state."""

    def adapt(self, report):
        outcome = super().adapt(report)
        if outcome.passed is True:
            return replace(outcome, candidate_assessment=None)
        return outcome


def _repository_effect_audit(details: dict[str, Any]) -> dict[str, Any] | None:
    direct = details.get("repository_effect_audit")
    if isinstance(direct, dict):
        return direct
    report_details = details.get("report_details")
    if isinstance(report_details, dict):
        nested = report_details.get("repository_effect_audit")
        if isinstance(nested, dict):
            return nested
    return None


def _goal_status(details: dict[str, Any]) -> str:
    value = details.get("goal_passed")
    if value is True:
        return "satisfied"
    if value is False:
        return "unsatisfied"
    return "unknown"


def _effect_violations(audit: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(audit, dict):
        return []
    violations = audit.get("violations")
    if isinstance(violations, list):
        return [item for item in violations if isinstance(item, dict)]
    return []


def _base_operation_violations(
    details: dict[str, Any],
    summary: str,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    protected = details.get("protected_environment_violation")
    if isinstance(protected, dict):
        violations.append(
            {
                "kind": "protected_environment",
                **protected,
            }
        )
    outer_workspace = details.get("outer_workspace_violation")
    if isinstance(outer_workspace, dict):
        violations.append(
            {
                "kind": "outer_workspace_effect",
                **outer_workspace,
            }
        )
    import_alias = details.get("import_alias_audit")
    if isinstance(import_alias, dict) and import_alias.get("valid") is not True:
        raw_alias_violations = import_alias.get("violations")
        if isinstance(raw_alias_violations, list) and raw_alias_violations:
            violations.extend(
                {
                    "kind": "synthetic_import_alias",
                    **item,
                }
                for item in raw_alias_violations
                if isinstance(item, dict)
            )
        else:
            violations.append({"kind": "synthetic_import_alias"})
    if summary == "Candidate did not return control to the executable goal":
        violations.append({"kind": "candidate_completion"})
    return violations


class StatefulExecutableGoalVerifierV24(StatefulExecutableGoalVerifierV23):
    """Preserve goal evidence while enforcing the candidate's caller contract."""

    check_profile = "executable-goal-contract-v3.4"

    def __init__(
        self,
        contract: ExecutableGoalContract,
        *,
        compact_findings: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            contract,
            compact_findings=compact_findings,
            **kwargs,
        )
        if not compact_findings:
            self.finding_adapter = _TerminalPassFindingAdapter()

    def _effect_audit(self, handle, result):
        value, failure = super()._effect_audit(handle, result)
        if (
            failure is not None
            and isinstance(value, dict)
            and value.get("valid") is False
        ):
            return value, None
        return value, failure

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
        completion_command = (
            f"printf '%s\\n' {shlex.quote(completion_marker)}"
        )
        if command.count(completion_command) != 1:
            raise RuntimeError(
                "V2.4 could not locate the candidate completion boundary"
            )
        cwd_observation = (
            f"printf '{_CANDIDATE_CWD_PREFIX}%s\\n' \"$PWD\""
        )
        return (
            command.replace(
                completion_command,
                f"{cwd_observation}\n{completion_command}",
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
        outcome = super().verify(candidate, environment)
        handle = environment.handle
        if not isinstance(handle, DockerEnvironmentHandle):
            raise ValueError("V2.4 goal verifier requires a Docker environment handle")

        cwd_matches = list(_CANDIDATE_CWD.finditer(outcome.bootstrap.stdout))
        observed_cwd = (
            cwd_matches[-1].group("path") if cwd_matches else None
        )
        cwd_valid = observed_cwd == handle.container_workdir
        audit = _repository_effect_audit(outcome.details)
        effect_valid = audit is None or audit.get("valid") is True
        violations = [
            *_effect_violations(audit),
            *_base_operation_violations(outcome.details, outcome.summary),
        ]
        if not cwd_valid:
            violations.append(
                {
                    "kind": "shell_postcondition",
                    "name": "working_directory",
                    "required": handle.container_workdir,
                    "observed": observed_cwd,
                }
            )
        operation_valid = effect_valid and cwd_valid and not violations
        operation_contract = {
            "schema": "envsolve-operation-postconditions-v1",
            "status": "satisfied" if operation_valid else "violated",
            "valid": operation_valid,
            "goal_status": _goal_status(outcome.details),
            "repository_effect_valid": (
                audit.get("valid") if isinstance(audit, dict) else None
            ),
            "shell_postconditions": {
                "working_directory": {
                    "required": handle.container_workdir,
                    "observed": observed_cwd,
                    "satisfied": cwd_valid,
                }
            },
            "violations": violations,
        }
        details = {
            **outcome.details,
            "goal_status": operation_contract["goal_status"],
            "operation_contract": operation_contract,
        }
        if operation_valid:
            return replace(outcome, details=details)

        first = violations[0] if violations else {"kind": "unknown"}
        label = str(first.get("kind", "operation_postcondition"))
        path = first.get("path") or first.get("name")
        if path:
            label = f"{label}: {path}"
        assessment = outcome.candidate_assessment
        if assessment is not None:
            assessment = CandidateAssessment(
                admissible=False,
                unresolved_constraints=assessment.unresolved_constraints,
                satisfied_constraints=assessment.satisfied_constraints,
                unknown_constraints=assessment.unknown_constraints,
                reason="candidate violated an operation postcondition",
            )
        return replace(
            outcome,
            passed=False,
            summary=(
                "Candidate satisfied the executable goal but violated operation "
                f"postconditions ({label})"
                if operation_contract["goal_status"] == "satisfied"
                else f"Candidate violated operation postconditions ({label})"
            ),
            hypotheses=(
                *outcome.hypotheses,
                HypothesisEvidence(
                    hypothesis_id="hypothesis-operation-postconditions",
                    statement=(
                        "The cumulative deployment program must preserve its "
                        "caller-visible operation postconditions"
                    ),
                    value=operation_contract,
                    confidence=1.0,
                ),
            ),
            observations=(
                *outcome.observations,
                ObservationEvidence(
                    "candidate-integrity-observation",
                    {
                        "integrity_valid": False,
                        "kind": "operation-postcondition",
                        "violations": violations,
                    },
                    1.0,
                ),
            ),
            details=details,
            candidate_assessment=assessment,
        )
