from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import re
from typing import Any, Callable, Iterable

from envsolve.constraints import (
    ConstraintDomain,
    ConstraintPredicate,
    ConstraintRole,
    EvidenceNormalizer,
)
from envsolve.controller.outcomes import (
    ReplayObservation,
    ReplayOutcome,
    ReplayOutcomePolicy,
)
from envsolve.solver import CommandResult, FeedbackChannel
from envsolve.verification import (
    FindingDisposition,
    StructuredVerifierFinding,
    StructuredVerifierReport,
)
from envsolve.verification.imports import (
    EnvironmentFacts,
    ExclusionRule,
    ImportContextAnalyzer,
    ImportDisposition,
    MissingImportFinding,
)


MISSING_IMPORT_MESSAGE = re.compile(r'^Import "([^"]+)" could not be resolved$')
PROJECT_PREFIX = "/data/project/"


def _finding_id(kind: str, value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return f"{kind}-{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def _relative_project_file(value: object) -> str | None:
    path = str(value)
    if not path.startswith(PROJECT_PREFIX):
        return None
    relative = path[len(PROJECT_PREFIX) :]
    if not relative or relative.startswith("/") or ".." in relative.split("/"):
        return None
    return relative


def _disposition(value: ImportDisposition) -> FindingDisposition:
    return (
        FindingDisposition.UNKNOWN
        if value is ImportDisposition.UNRESOLVED
        else FindingDisposition.ACTIVE
    )


class EnvBenchFindingCollector:
    """Collect typed failures from one completed EnvBench fresh replay."""

    schema = "envsolve-envbench-finding-collector-v1"

    def __init__(
        self,
        facts: EnvironmentFacts,
        exclusions: Iterable[ExclusionRule] = (),
        import_analyzer: ImportContextAnalyzer | None = None,
        evidence_normalizer: EvidenceNormalizer | None = None,
        outcome_policy: ReplayOutcomePolicy | None = None,
    ) -> None:
        self.facts = facts
        self.exclusions = tuple(exclusions)
        self.import_analyzer = import_analyzer or ImportContextAnalyzer()
        self.evidence_normalizer = evidence_normalizer or EvidenceNormalizer()
        self.outcome_policy = outcome_policy or ReplayOutcomePolicy()

    def _bootstrap_findings(self, logs: str) -> tuple[StructuredVerifierFinding, ...]:
        constraints = self.evidence_normalizer.normalize(
            "envbench-bootstrap-log",
            {
                "kind": "action-result",
                "value": {
                    "exit_code": 1,
                    "stdout": "",
                    "stderr": logs,
                    "deterministic_counterexample": True,
                },
                "confidence": 1.0,
            },
        )
        grouped: dict[tuple[str, str, str], list] = defaultdict(list)
        for item in constraints:
            grouped[(item.domain.value, item.subject, item.predicate.value)].append(item)
        findings: list[StructuredVerifierFinding] = []
        for key, values in sorted(grouped.items()):
            requirements = [
                item for item in values if item.role is ConstraintRole.REQUIREMENT
            ]
            facts = [item for item in values if item.role is ConstraintRole.FACT]
            payload = {"domain": key[0], "subject": key[1], "predicate": key[2]}
            if len(requirements) != 1 or len(facts) != 1:
                findings.append(
                    StructuredVerifierFinding(
                        finding_id=_finding_id("bootstrap-unknown", payload),
                        domain=values[0].domain,
                        subject=values[0].subject,
                        predicate=values[0].predicate,
                        required=values[0].value,
                        observed=None,
                        disposition=FindingDisposition.UNKNOWN,
                        provenance={
                            "collector": self.schema,
                            "reason": "bootstrap constraints did not form one requirement/fact pair",
                        },
                    )
                )
                continue
            findings.append(
                StructuredVerifierFinding(
                    finding_id=_finding_id("bootstrap", payload),
                    domain=requirements[0].domain,
                    subject=requirements[0].subject,
                    predicate=requirements[0].predicate,
                    required=requirements[0].value,
                    observed=facts[0].value,
                    disposition=FindingDisposition.ACTIVE,
                    provenance={
                        "collector": self.schema,
                        "source": "generic-action-result-normalizer",
                    },
                )
            )
        return tuple(findings)

    def _unknown_import(
        self,
        module: str,
        path: str | None,
        line: int | None,
        reason: str,
    ) -> StructuredVerifierFinding:
        payload = {"module": module, "file": path, "line": line, "reason": reason}
        return StructuredVerifierFinding(
            finding_id=_finding_id("missing-import-unknown", payload),
            domain=ConstraintDomain.MODULE,
            subject=module or "unparsed-missing-import",
            predicate=ConstraintPredicate.PRESENT,
            required=True,
            observed=False,
            disposition=FindingDisposition.UNKNOWN,
            provenance={"collector": self.schema, **payload},
        )

    def _import_findings(
        self,
        diagnostics: list[dict[str, Any]],
        source_loader: Callable[[str], str],
    ) -> tuple[StructuredVerifierFinding, ...]:
        findings: list[StructuredVerifierFinding] = []
        for diagnostic in diagnostics:
            message = str(diagnostic.get("message", ""))
            match = MISSING_IMPORT_MESSAGE.fullmatch(message)
            path = _relative_project_file(diagnostic.get("file", ""))
            range_value = diagnostic.get("range")
            start = range_value.get("start") if isinstance(range_value, dict) else None
            line = start.get("line") if isinstance(start, dict) else None
            if match is None or path is None or isinstance(line, bool) or not isinstance(line, int):
                findings.append(
                    self._unknown_import(
                        match.group(1) if match else "unparsed-missing-import",
                        path,
                        line if isinstance(line, int) and not isinstance(line, bool) else None,
                        "malformed missing-import diagnostic",
                    )
                )
                continue
            module = match.group(1)
            try:
                source = source_loader(path)
                if not isinstance(source, str):
                    raise TypeError("source loader returned non-text content")
                assessment = self.import_analyzer.assess(
                    MissingImportFinding(module, path, line, message),
                    source,
                    self.facts,
                    self.exclusions,
                )
                disposition = _disposition(assessment.disposition)
                provenance = {
                    "collector": self.schema,
                    "file": path,
                    "line": line,
                    "role": assessment.role.value,
                    "import_disposition": assessment.disposition.value,
                    "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "assessment_evidence": [item.__dict__ for item in assessment.evidence],
                }
            except (LookupError, OSError, TypeError, UnicodeError, ValueError) as exc:
                findings.append(
                    self._unknown_import(
                        module,
                        path,
                        line,
                        f"{type(exc).__name__}: {exc}",
                    )
                )
                continue
            payload = {"module": module, "file": path, "line": line}
            findings.append(
                StructuredVerifierFinding(
                    finding_id=_finding_id("missing-import", payload),
                    domain=ConstraintDomain.MODULE,
                    subject=module,
                    predicate=ConstraintPredicate.PRESENT,
                    required=True,
                    observed=False,
                    disposition=disposition,
                    provenance=provenance,
                )
            )
        return tuple(findings)

    def collect(
        self,
        raw: dict[str, Any],
        *,
        expected_repository: str,
        expected_revision: str,
        environment_id: str,
        environment_fresh: bool,
        evaluation_completed: bool,
        source_loader: Callable[[str], str],
        infrastructure_error: str | None = None,
    ) -> StructuredVerifierReport:
        identity_matches = (
            raw.get("repo_name") == expected_repository
            and raw.get("commit_sha") == expected_revision
        )
        raw_exit_code = raw.get("exit_code")
        exit_code_valid = isinstance(raw_exit_code, int) and not isinstance(
            raw_exit_code, bool
        )
        exit_code = int(raw_exit_code) if exit_code_valid else 255
        raw_issues = raw.get("issues_count")
        issues_valid = isinstance(raw_issues, int) and not isinstance(raw_issues, bool)
        logs = str(raw.get("container_logs", ""))
        completed = evaluation_completed and identity_matches and exit_code_valid and issues_valid
        goal_passed = exit_code == 0 and raw_issues == 0 if completed else None

        if infrastructure_error is None and exit_code != 0:
            classified = self.outcome_policy.classify(
                ReplayObservation(exit_code, 0, False, logs)
            )
            if classified is ReplayOutcome.INFRASTRUCTURE_BLOCKED:
                infrastructure_error = "network failure signature in bootstrap logs"

        findings: tuple[StructuredVerifierFinding, ...] = ()
        diagnostics: list[dict[str, Any]] = []
        count_matches = True
        if completed and exit_code != 0:
            findings = self._bootstrap_findings(logs)
        elif completed:
            pyright = raw.get("pyright")
            values = pyright.get("generalDiagnostics") if isinstance(pyright, dict) else None
            if isinstance(values, list):
                diagnostics = [item for item in values if isinstance(item, dict)]
            missing = [
                item
                for item in diagnostics
                if item.get("rule") == "reportMissingImports"
            ]
            count_matches = len(missing) == raw_issues
            findings = self._import_findings(missing, source_loader)
            if not count_matches:
                findings = (
                    *findings,
                    self._unknown_import(
                        "diagnostic-count-mismatch",
                        None,
                        None,
                        f"issues_count={raw_issues}, diagnostics={len(missing)}",
                    ),
                )

        return StructuredVerifierReport(
            verifier="envbench-official-with-p5-context-v1",
            check_profile="envbench-official-diagnostics-v1",
            channel=FeedbackChannel.POST_EPISODE_EVALUATION,
            environment_id=environment_id,
            environment_fresh=environment_fresh,
            bootstrap=CommandResult(exit_code, stderr=logs),
            completed=completed,
            goal_passed=goal_passed,
            findings=findings,
            infrastructure_error=infrastructure_error,
            details={
                "collector_schema": self.schema,
                "identity_matches": identity_matches,
                "exit_code_valid": exit_code_valid,
                "issues_count_valid": issues_valid,
                "issues_count": raw_issues,
                "missing_import_diagnostic_count": sum(
                    item.get("rule") == "reportMissingImports" for item in diagnostics
                ),
                "diagnostic_count_matches": count_matches,
                "non_missing_import_error_count": sum(
                    item.get("severity") == "error"
                    and item.get("rule") != "reportMissingImports"
                    for item in diagnostics
                ),
            },
        )
