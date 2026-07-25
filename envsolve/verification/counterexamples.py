from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from typing import Any

from envsolve.constraints.models import ConstraintDomain, ConstraintPredicate
from envsolve.solver import (
    CandidateAssessment,
    CommandResult,
    CounterexampleEvidence,
    ExecutableVerification,
    FeedbackChannel,
    HypothesisEvidence,
    ObservationEvidence,
)


class FindingDisposition(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SATISFIED = "satisfied"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class StructuredVerifierFinding:
    finding_id: str
    domain: ConstraintDomain
    subject: str
    predicate: ConstraintPredicate
    required: str | bool
    observed: str | bool | None
    disposition: FindingDisposition
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.finding_id, str) or not self.finding_id.strip():
            raise ValueError("Structured finding identifier cannot be empty")
        if not isinstance(self.subject, str) or not self.subject.strip():
            raise ValueError("Structured finding subject cannot be empty")
        if not isinstance(self.domain, ConstraintDomain):
            raise ValueError("Structured finding domain must be typed")
        if not isinstance(self.predicate, ConstraintPredicate):
            raise ValueError("Structured finding predicate must be typed")
        if not isinstance(self.disposition, FindingDisposition):
            raise ValueError("Structured finding disposition must be typed")
        if self.disposition in {
            FindingDisposition.ACTIVE,
            FindingDisposition.SATISFIED,
        } and self.observed is None:
            raise ValueError("Active and satisfied findings require an observed value")
        if not isinstance(self.provenance, dict):
            raise ValueError("Structured finding provenance must be an object")
        try:
            json.dumps(self.provenance, ensure_ascii=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("Structured finding provenance must be JSON serializable") from exc
        self._validate_values()

    def _validate_values(self) -> None:
        if self.predicate is ConstraintPredicate.PRESENT:
            if not isinstance(self.required, bool) or (
                self.observed is not None and not isinstance(self.observed, bool)
            ):
                raise ValueError("Presence findings require boolean values")
        elif self.predicate in {
            ConstraintPredicate.VERSION,
            ConstraintPredicate.EQUALS,
        }:
            if not isinstance(self.required, str) or (
                self.observed is not None and not isinstance(self.observed, str)
            ):
                raise ValueError("Version and equality findings require string values")


@dataclass(frozen=True)
class StructuredVerifierReport:
    verifier: str
    check_profile: str
    channel: FeedbackChannel
    environment_id: str
    environment_fresh: bool
    bootstrap: CommandResult
    completed: bool
    goal_passed: bool | None
    findings: tuple[StructuredVerifierFinding, ...] = ()
    infrastructure_error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.completed, bool):
            raise ValueError("Structured verifier completion must be boolean")
        if self.goal_passed is not None and not isinstance(self.goal_passed, bool):
            raise ValueError("Structured verifier goal decision must be boolean or null")
        if not isinstance(self.findings, tuple) or not all(
            isinstance(item, StructuredVerifierFinding) for item in self.findings
        ):
            raise ValueError("Structured verifier findings must be typed")
        identifiers = [item.finding_id for item in self.findings]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Structured verifier finding identifiers must be unique")
        if self.infrastructure_error is not None and (
            not isinstance(self.infrastructure_error, str)
            or not self.infrastructure_error.strip()
        ):
            raise ValueError("Infrastructure error cannot be empty")
        if not isinstance(self.details, dict):
            raise ValueError("Structured verifier report details must be an object")
        try:
            json.dumps(self.details, ensure_ascii=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("Structured verifier details must be JSON serializable") from exc
        if not isinstance(self.channel, FeedbackChannel):
            raise ValueError("Structured verifier channel must be typed")


class StructuredFindingAdapter:
    """Convert verifier-owned typed findings into solver-owned evidence."""

    schema = "envsolve-structured-finding-adapter-v3"

    @staticmethod
    def _evidence_kind(domain: ConstraintDomain, role: str) -> str:
        if domain is ConstraintDomain.RUNTIME:
            return f"python-{role}"
        return f"{domain.value}-{role}"

    @staticmethod
    def _evidence_value(
        finding: StructuredVerifierFinding,
        value: str | bool,
        role: str,
    ) -> dict[str, Any]:
        provenance = {
            "finding_id": finding.finding_id,
            "finding_provenance": finding.provenance,
        }
        if finding.predicate is ConstraintPredicate.VERSION:
            if finding.domain not in {
                ConstraintDomain.RUNTIME,
                ConstraintDomain.PACKAGE,
            }:
                raise ValueError("Version findings support only runtime or package domains")
            key = "specifier" if role == "requirement" else "version"
            return {"name": finding.subject, key: value, **provenance}
        if finding.predicate is ConstraintPredicate.PRESENT:
            if finding.domain not in {
                ConstraintDomain.PACKAGE,
                ConstraintDomain.CAPABILITY,
                ConstraintDomain.MODULE,
            }:
                raise ValueError("Presence findings have an unsupported domain")
            return {"name": finding.subject, "present": value, **provenance}
        if (
            finding.predicate is ConstraintPredicate.EQUALS
            and finding.domain is ConstraintDomain.PLATFORM
        ):
            return {"name": finding.subject, "value": value, **provenance}
        raise ValueError("Structured finding predicate/domain combination is unsupported")

    def _counterexamples(
        self, findings: tuple[StructuredVerifierFinding, ...]
    ) -> tuple[CounterexampleEvidence, ...]:
        evidence: list[CounterexampleEvidence] = []
        for finding in findings:
            if finding.disposition is not FindingDisposition.ACTIVE:
                continue
            if finding.observed is None:
                raise ValueError("Active finding has no observed value")
            evidence.extend(
                (
                    CounterexampleEvidence(
                        self._evidence_kind(finding.domain, "requirement"),
                        self._evidence_value(finding, finding.required, "requirement"),
                    ),
                    CounterexampleEvidence(
                        self._evidence_kind(finding.domain, "observation"),
                        self._evidence_value(finding, finding.observed, "observation"),
                    ),
                )
            )
        return tuple(evidence)

    def _observations(
        self, findings: tuple[StructuredVerifierFinding, ...]
    ) -> tuple[ObservationEvidence, ...]:
        return tuple(
            ObservationEvidence(
                self._evidence_kind(finding.domain, "observation"),
                self._evidence_value(finding, finding.observed, "observation"),
            )
            for finding in findings
            if finding.disposition is FindingDisposition.SATISFIED
            and finding.observed is not None
        )

    @staticmethod
    def _hypotheses(
        findings: tuple[StructuredVerifierFinding, ...]
    ) -> tuple[HypothesisEvidence, ...]:
        return tuple(
            HypothesisEvidence(
                hypothesis_id=f"hypothesis-{finding.finding_id}",
                statement=(
                    f"{finding.domain.value}:{finding.subject}:"
                    f"{finding.predicate.value} remains unresolved"
                ),
                value={
                    "required": finding.required,
                    "observed": finding.observed,
                    "provenance": finding.provenance,
                },
                confidence=0.5,
            )
            for finding in findings
        )

    def adapt(self, report: StructuredVerifierReport) -> ExecutableVerification:
        active = tuple(
            item
            for item in report.findings
            if item.disposition is FindingDisposition.ACTIVE
        )
        unknown = tuple(
            item
            for item in report.findings
            if item.disposition is FindingDisposition.UNKNOWN
        )
        inactive_count = sum(
            item.disposition is FindingDisposition.INACTIVE for item in report.findings
        )
        satisfied = tuple(
            item
            for item in report.findings
            if item.disposition is FindingDisposition.SATISFIED
        )
        summary = (
            f"structured verifier: goal={report.goal_passed}, active={len(active)}, "
            f"satisfied={len(satisfied)}, unknown={len(unknown)}, "
            f"inactive={inactive_count}, "
            f"bootstrap={report.bootstrap.exit_code}"
        )
        infrastructure_unknown = (
            report.infrastructure_error is not None
            or not report.completed
            or report.goal_passed is None
        )
        if infrastructure_unknown or (report.goal_passed is True and unknown):
            passed: bool | None = None
            observations: tuple[ObservationEvidence, ...] = ()
            counterexamples: tuple[CounterexampleEvidence, ...] = ()
        else:
            passed = report.goal_passed
            observations = self._observations(satisfied)
            counterexamples = self._counterexamples(active)
        evidence_scope_id = report.details.get("evidence_scope_id")
        if evidence_scope_id is not None and (
            not isinstance(evidence_scope_id, str) or not evidence_scope_id
        ):
            raise ValueError("Verifier evidence_scope_id must be a non-empty string")
        finding_set_complete = report.details.get("finding_set_complete", False)
        if not isinstance(finding_set_complete, bool):
            raise ValueError("Verifier finding_set_complete must be a boolean")
        if finding_set_complete and evidence_scope_id is None:
            raise ValueError(
                "Complete verifier finding sets require an evidence_scope_id"
            )
        return ExecutableVerification(
            verifier=report.verifier,
            check_profile=report.check_profile,
            channel=report.channel,
            passed=passed,
            bootstrap=report.bootstrap,
            summary=summary,
            observations=observations,
            counterexamples=counterexamples,
            hypotheses=self._hypotheses(unknown),
            details={
                "adapter_schema": self.schema,
                "completed": report.completed,
                "goal_passed": report.goal_passed,
                "infrastructure_error": report.infrastructure_error,
                "finding_ids": [item.finding_id for item in report.findings],
                "finding_dispositions": {
                    item.finding_id: item.disposition.value for item in report.findings
                },
                "report_details": report.details,
                **(
                    {"evidence_scope_id": evidence_scope_id}
                    if evidence_scope_id is not None
                    else {}
                ),
                "finding_set_complete": finding_set_complete,
            },
            candidate_assessment=CandidateAssessment(
                admissible=(
                    report.completed
                    and report.infrastructure_error is None
                    and report.bootstrap.exit_code == 0
                    and report.goal_passed is False
                    and bool(active)
                    and not unknown
                ),
                unresolved_constraints=len(active),
                satisfied_constraints=len(satisfied),
                unknown_constraints=len(unknown),
                reason=(
                    "complete replay with unresolved internal constraints"
                    if report.completed
                    and report.infrastructure_error is None
                    and report.bootstrap.exit_code == 0
                    and report.goal_passed is False
                    else "candidate replay is certified, incomplete, or failed execution"
                ),
            ),
        )
