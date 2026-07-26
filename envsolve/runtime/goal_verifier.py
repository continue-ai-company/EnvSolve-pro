from __future__ import annotations

import json
from pathlib import Path
from pathlib import PurePosixPath
import re
import shlex
import subprocess
import time
from typing import Any, Callable, Protocol
import uuid

from envsolve.constraints.models import ConstraintDomain, ConstraintPredicate
from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.runtime.integrity import (
    IMPORT_ALIAS_AUDIT_MARKER,
    marked_json_payload,
    python_import_alias_audit_command,
)
from envsolve.solver import (
    CommandResult,
    DeploymentCandidate,
    ExecutableVerification,
    FeedbackChannel,
    HypothesisEvidence,
    ObservationEvidence,
    ProvisionedEnvironment,
)
from envsolve.verification.counterexamples import (
    FindingDisposition,
    StructuredFindingAdapter,
    StructuredVerifierFinding,
    StructuredVerifierReport,
)


RunCommand = Callable[..., subprocess.CompletedProcess[str]]


class EffectAuditReport(Protocol):
    @property
    def valid(self) -> bool: ...

    def to_dict(self) -> dict[str, Any]: ...


EffectAuditor = Callable[[Path], EffectAuditReport]
_CANDIDATE_COMPLETION_PREFIX = "ENVSOLVE_GOAL_CANDIDATE_COMPLETED_V1="
_OUTER_WORKSPACE_VIOLATION_PREFIX = (
    "ENVSOLVE_GOAL_OUTER_WORKSPACE_VIOLATION_V1="
)
_PROTECTED_ENVIRONMENT_VIOLATION_PREFIX = (
    "ENVSOLVE_GOAL_PROTECTED_ENVIRONMENT_VIOLATION_V1="
)
_FAILED_ACTION = re.compile(
    r"^ENVSOLVE_GOAL_CANDIDATE_FAILED_V1=(?P<exit_code>[0-9]+)$",
    re.MULTILINE,
)
_OUTER_WORKSPACE_VIOLATION = re.compile(
    rf"^{_OUTER_WORKSPACE_VIOLATION_PREFIX}(?P<path>[^\r\n]+)$",
    re.MULTILINE,
)
_PROTECTED_ENVIRONMENT_VIOLATION = re.compile(
    rf"^{_PROTECTED_ENVIRONMENT_VIOLATION_PREFIX}(?P<name>[A-Za-z_][A-Za-z0-9_]*)$",
    re.MULTILINE,
)


class ExecutableGoalContractVerifier:
    """Execute a candidate and its public goal contract in one fresh shell."""

    check_profile = "executable-goal-contract-v2"

    def __init__(
        self,
        contract: ExecutableGoalContract,
        *,
        observation_timeout: int = 900,
        effect_auditor: EffectAuditor | None = None,
        run_command: RunCommand = subprocess.run,
    ) -> None:
        if not isinstance(observation_timeout, int) or observation_timeout <= 0:
            raise ValueError("Goal observation timeout must be a positive integer")
        self.contract = contract
        self.observation_timeout = observation_timeout
        self.effect_auditor = effect_auditor
        self.run_command = run_command
        self.finding_adapter = StructuredFindingAdapter()

    @staticmethod
    def _command_result(
        process: subprocess.CompletedProcess[str],
        started: float,
    ) -> CommandResult:
        return CommandResult(
            process.returncode,
            process.stdout,
            process.stderr,
            time.monotonic() - started,
        )

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
                "trap 'rc=$?; printf \"ENVSOLVE_GOAL_CANDIDATE_FAILED_V1=%s\\n\" "
                "\"$rc\" >&2; exit \"$rc\"' ERR"
            ),
            candidate.script.rstrip(),
            (
                f"for ENVSOLVE_PROTECTED_PREFIX in {protected_prefixes}; do "
                "while IFS='=' read -r ENVSOLVE_ENV_NAME _; do "
                "case \"$ENVSOLVE_ENV_NAME\" in "
                "\"$ENVSOLVE_PROTECTED_PREFIX\"*) "
                f"printf '{_PROTECTED_ENVIRONMENT_VIOLATION_PREFIX}%s\\n' "
                "\"$ENVSOLVE_ENV_NAME\" >&2; exit 254 ;; "
                "esac; "
                "done < <(/usr/bin/env); "
                "done"
                if protected_prefixes
                else ":"
            ),
            f"ENVSOLVE_OUTER_WORKSPACE={shlex.quote(outer_workspace)}",
            (
                "if [ -d \"$ENVSOLVE_OUTER_WORKSPACE\" ]; then "
                "ENVSOLVE_UNEXPECTED_OUTER_PATH=$("
                "/usr/bin/find \"$ENVSOLVE_OUTER_WORKSPACE\" "
                "-mindepth 1 -maxdepth 1 "
                f"! -path {shlex.quote(handle.container_workdir)} "
                "-print -quit"
                "); "
                "if [ -n \"$ENVSOLVE_UNEXPECTED_OUTER_PATH\" ]; then "
                f"printf '{_OUTER_WORKSPACE_VIOLATION_PREFIX}%s\\n' "
                "\"$ENVSOLVE_UNEXPECTED_OUTER_PATH\" >&2; "
                "exit 253; "
                "fi; "
                "fi"
            ),
            f"printf '%s\\n' {shlex.quote(completion_marker)}",
            python_import_alias_audit_command(handle.container_workdir),
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

    @staticmethod
    def _extract_report(stdout: str, begin: str, nonce: str) -> dict[str, Any] | None:
        end = f"\nENVSOLVE_GOAL_REPORT_END_V1={nonce}"
        if stdout.count(begin) != 1 or stdout.count(end) != 1:
            return None
        encoded = stdout.split(begin, 1)[1].split(end, 1)[0].strip()
        if not encoded:
            return None
        try:
            value = json.loads(encoded)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None

    def _effect_audit(
        self,
        handle: DockerEnvironmentHandle,
        result: CommandResult,
    ) -> tuple[dict[str, Any] | None, ExecutableVerification | None]:
        if self.effect_auditor is None:
            return None, None
        try:
            report = self.effect_auditor(handle.worktree)
            value = report.to_dict()
        except Exception as exc:
            return None, self._unknown(
                result,
                "Candidate effect audit did not complete",
                {"effect_audit_error": f"{type(exc).__name__}: {exc}"},
            )
        if report.valid:
            return value, None
        return value, ExecutableVerification(
            verifier="envsolve-executable-goal-verifier",
            check_profile=self.check_profile,
            channel=FeedbackChannel.INTERNAL_EXECUTION,
            passed=False,
            bootstrap=result,
            summary="Candidate violated repository or workspace effect boundaries",
            hypotheses=(
                HypothesisEvidence(
                    hypothesis_id="hypothesis-goal-contract-inadmissible-effect",
                    statement="The candidate must preserve repository and adapter-owned state",
                    value={"repository_effect_audit": value},
                    confidence=1.0,
                ),
            ),
            details=self._details(repository_effect_audit=value),
        )

    def _details(self, **extra: Any) -> dict[str, Any]:
        return {
            "evidence_scope_id": (
                f"goal-contract:{self.contract.contract_id}:{self.contract.sha256}"
            ),
            "goal_contract": {
                "contract_id": self.contract.contract_id,
                "description": self.contract.description,
                "report_schema": self.contract.report_schema,
                "sha256": self.contract.sha256,
            },
            **extra,
        }

    def _unknown(
        self,
        result: CommandResult,
        summary: str,
        details: dict[str, Any],
    ) -> ExecutableVerification:
        return ExecutableVerification(
            verifier="envsolve-executable-goal-verifier",
            check_profile=self.check_profile,
            channel=FeedbackChannel.INTERNAL_EXECUTION,
            passed=None,
            bootstrap=result,
            summary=summary,
            hypotheses=(
                HypothesisEvidence(
                    hypothesis_id="hypothesis-goal-contract-unknown",
                    statement="The executable goal observation is incomplete",
                    value=details,
                    confidence=1.0,
                ),
            ),
            details=self._details(**details),
        )

    def verify(
        self,
        candidate: DeploymentCandidate,
        environment: ProvisionedEnvironment,
    ) -> ExecutableVerification:
        handle = environment.handle
        if not isinstance(handle, DockerEnvironmentHandle):
            raise ValueError("Goal contract verifier requires a Docker environment handle")
        nonce = uuid.uuid4().hex
        command, completion_marker, report_begin = self._command(
            candidate,
            handle,
            nonce,
        )
        started = time.monotonic()
        try:
            process = self.run_command(
                [
                    "docker",
                    "exec",
                    "--workdir",
                    handle.container_workdir,
                    handle.container_id,
                    "/bin/bash",
                    "-lc",
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=self.observation_timeout,
            )
            result = self._command_result(process, started)
        except subprocess.TimeoutExpired as exc:
            stdout = (
                exc.stdout.decode(errors="replace")
                if isinstance(exc.stdout, bytes)
                else (exc.stdout or "")
            )
            stderr = (
                exc.stderr.decode(errors="replace")
                if isinstance(exc.stderr, bytes)
                else (exc.stderr or "")
            )
            result = CommandResult(
                124,
                stdout,
                f"{stderr}\nExecutable goal contract timed out".strip(),
                time.monotonic() - started,
            )
            return self._unknown(
                result,
                "Executable goal contract exceeded its observation timeout",
                {
                    "execution_timeout": True,
                    "observation_timeout_seconds": self.observation_timeout,
                },
            )

        effect_audit, audit_failure = self._effect_audit(handle, result)
        if audit_failure is not None:
            return audit_failure
        protected_environment_violation = _PROTECTED_ENVIRONMENT_VIOLATION.search(
            result.stderr
        )
        if protected_environment_violation is not None:
            name = protected_environment_violation.group("name")
            return ExecutableVerification(
                verifier="envsolve-executable-goal-verifier",
                check_profile=self.check_profile,
                channel=FeedbackChannel.INTERNAL_EXECUTION,
                passed=False,
                bootstrap=result,
                summary=(
                    "Candidate modified a goal-protected environment surface"
                ),
                hypotheses=(
                    HypothesisEvidence(
                        hypothesis_id=(
                            "hypothesis-goal-contract-protected-environment"
                        ),
                        statement=(
                            "The candidate must not influence the executable "
                            "goal through protected environment variables"
                        ),
                        value={"environment_variable": name},
                        confidence=1.0,
                    ),
                ),
                details=self._details(
                    repository_effect_audit=effect_audit,
                    protected_environment_violation={"name": name},
                ),
            )
        outer_workspace_violation = _OUTER_WORKSPACE_VIOLATION.search(result.stderr)
        if outer_workspace_violation is not None:
            path = outer_workspace_violation.group("path")
            return ExecutableVerification(
                verifier="envsolve-executable-goal-verifier",
                check_profile=self.check_profile,
                channel=FeedbackChannel.INTERNAL_EXECUTION,
                passed=False,
                bootstrap=result,
                summary=(
                    "Candidate modified the adapter-owned outer workspace"
                ),
                hypotheses=(
                    HypothesisEvidence(
                        hypothesis_id=(
                            "hypothesis-goal-contract-outer-workspace-effect"
                        ),
                        statement=(
                            "The candidate must keep all generated state inside "
                            "the project or temporary workspace"
                        ),
                        value={"unexpected_path": path},
                        confidence=1.0,
                    ),
                ),
                details=self._details(
                    repository_effect_audit=effect_audit,
                    outer_workspace_violation={"path": path},
                ),
            )
        if completion_marker not in result.stdout:
            return ExecutableVerification(
                verifier="envsolve-executable-goal-verifier",
                check_profile=self.check_profile,
                channel=FeedbackChannel.INTERNAL_EXECUTION,
                passed=False,
                bootstrap=result,
                summary="Candidate did not return control to the executable goal",
                hypotheses=(
                    HypothesisEvidence(
                        hypothesis_id="hypothesis-goal-contract-candidate-failure",
                        statement="The complete deployment candidate must execute successfully",
                        value={
                            "exit_code": result.exit_code,
                            "failed_action": bool(_FAILED_ACTION.search(result.stderr)),
                        },
                        confidence=1.0,
                    ),
                ),
                details=self._details(repository_effect_audit=effect_audit),
            )
        import_alias_audit = marked_json_payload(
            result.stdout,
            IMPORT_ALIAS_AUDIT_MARKER,
        )
        if import_alias_audit is None:
            return self._unknown(
                result,
                "Import alias integrity audit did not produce a valid report",
                {
                    "probe_marker": IMPORT_ALIAS_AUDIT_MARKER,
                    "repository_effect_audit": effect_audit,
                },
            )
        violations = import_alias_audit.get("violations")
        if (
            import_alias_audit.get("valid") is not True
            or not isinstance(violations, list)
            or violations
        ):
            return ExecutableVerification(
                verifier="envsolve-executable-goal-verifier",
                check_profile=self.check_profile,
                channel=FeedbackChannel.INTERNAL_EXECUTION,
                passed=False,
                bootstrap=result,
                summary="Candidate created a synthetic Python import alias",
                hypotheses=(
                    HypothesisEvidence(
                        hypothesis_id=(
                            "hypothesis-goal-contract-synthetic-import-alias"
                        ),
                        statement=(
                            "Import names must be provided by genuine project "
                            "or installed package artifacts"
                        ),
                        value={"import_alias_audit": import_alias_audit},
                        confidence=1.0,
                    ),
                ),
                observations=(
                    ObservationEvidence(
                        "candidate-integrity-observation",
                        {
                            "integrity_valid": False,
                            "kind": "synthetic-import-alias",
                            "violations": violations,
                        },
                        1.0,
                    ),
                ),
                details=self._details(
                    repository_effect_audit=effect_audit,
                    import_alias_audit=import_alias_audit,
                ),
            )

        payload = self._extract_report(result.stdout, report_begin, nonce)
        if result.exit_code != 0 or payload is None:
            return self._unknown(
                result,
                "Executable goal did not produce a valid report",
                {
                    "goal_exit_code": result.exit_code,
                    "report_observed": payload is not None,
                    "repository_effect_audit": effect_audit,
                },
            )
        try:
            report = self._structured_report(
                payload,
                result,
                environment,
                effect_audit,
            )
        except (KeyError, TypeError, ValueError) as exc:
            return self._unknown(
                result,
                "Executable goal report has an invalid schema",
                {
                    "report_error": f"{type(exc).__name__}: {exc}",
                    "repository_effect_audit": effect_audit,
                },
            )
        return self.finding_adapter.adapt(report)

    def _structured_report(
        self,
        payload: dict[str, Any],
        result: CommandResult,
        environment: ProvisionedEnvironment,
        effect_audit: dict[str, Any] | None,
    ) -> StructuredVerifierReport:
        if payload.get("schema") != self.contract.report_schema:
            raise ValueError("Goal report schema does not match the contract")
        status = payload.get("status")
        if status not in {"pass", "fail", "unknown"}:
            raise ValueError("Goal report status must be pass, fail, or unknown")
        finding_set_complete = payload.get("finding_set_complete", False)
        if not isinstance(finding_set_complete, bool):
            raise ValueError("Goal report finding_set_complete must be a boolean")
        raw_findings = payload.get("findings", [])
        if not isinstance(raw_findings, list):
            raise ValueError("Goal report findings must be an array")
        findings = tuple(
            self._finding(item, index)
            for index, item in enumerate(raw_findings)
        )
        if status == "pass" and any(
            item.disposition is FindingDisposition.ACTIVE for item in findings
        ):
            raise ValueError("Passing goal report cannot contain active findings")
        if status == "fail" and not any(
            item.disposition is FindingDisposition.ACTIVE for item in findings
        ):
            raise ValueError("Failing goal report requires an active finding")
        raw_details = payload.get("details", {})
        if not isinstance(raw_details, dict):
            raise ValueError("Goal report details must be an object")
        return StructuredVerifierReport(
            verifier="envsolve-executable-goal-verifier",
            check_profile=self.check_profile,
            channel=FeedbackChannel.INTERNAL_EXECUTION,
            environment_id=environment.receipt.environment_id,
            environment_fresh=True,
            bootstrap=result,
            completed=True,
            goal_passed=(
                True if status == "pass" else False if status == "fail" else None
            ),
            findings=findings,
            details=self._details(
                finding_set_complete=finding_set_complete,
                goal_report=payload,
                goal_report_details=raw_details,
                repository_effect_audit=effect_audit,
            ),
        )

    @staticmethod
    def _finding(value: Any, index: int) -> StructuredVerifierFinding:
        if not isinstance(value, dict):
            raise ValueError("Goal finding must be an object")
        domain = ConstraintDomain(value["domain"])
        predicate = ConstraintPredicate(value["predicate"])
        required = value["required"]
        observed = value.get("observed")
        disposition = (
            FindingDisposition.UNKNOWN
            if observed is None
            else FindingDisposition.SATISFIED
            if observed == required
            else FindingDisposition.ACTIVE
        )
        provenance = value.get("provenance", {})
        if not isinstance(provenance, dict):
            raise ValueError("Goal finding provenance must be an object")
        finding_id = value.get("finding_id", f"goal-finding-{index:04d}")
        return StructuredVerifierFinding(
            finding_id=finding_id,
            domain=domain,
            subject=value["subject"],
            predicate=predicate,
            required=required,
            observed=observed,
            disposition=disposition,
            provenance=provenance,
        )
