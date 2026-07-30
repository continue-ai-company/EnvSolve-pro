from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from typing import Any

from envsolve.constraints.models import ConstraintDomain, ConstraintPredicate
from envsolve.solver import ExecutableVerification
from envsolve.verification.counterexamples import (
    FindingDisposition,
    StructuredFindingAdapter,
    StructuredVerifierFinding,
    StructuredVerifierReport,
)


class RootObligationFindingAdapter(StructuredFindingAdapter):
    """Collapse repeated surface findings before they enter solver state."""

    schema = "envsolve-root-obligation-finding-adapter-v1"

    @staticmethod
    def _canonical_json(value: Any) -> str:
        return json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _root_subject(finding: StructuredVerifierFinding) -> str:
        if finding.domain is ConstraintDomain.MODULE:
            return finding.subject.split(".", 1)[0]
        return finding.subject

    def _group_findings(
        self,
        findings: tuple[StructuredVerifierFinding, ...],
    ) -> tuple[StructuredVerifierFinding, ...]:
        groups: dict[tuple[str, ...], list[StructuredVerifierFinding]] = {}
        for finding in findings:
            key = (
                finding.domain.value,
                self._root_subject(finding),
                finding.predicate.value,
                self._canonical_json(finding.required),
                self._canonical_json(finding.observed),
                finding.disposition.value,
            )
            groups.setdefault(key, []).append(finding)

        compacted: list[StructuredVerifierFinding] = []
        for key, members in sorted(groups.items()):
            domain, subject, predicate, required, observed, disposition = key
            surface_ids = sorted(item.finding_id for item in members)
            surface_subjects = sorted({item.subject for item in members})
            source_files = sorted(
                {
                    str(item.provenance["file"])
                    for item in members
                    if isinstance(item.provenance.get("file"), str)
                }
            )
            semantic = {
                "domain": domain,
                "subject": subject,
                "predicate": predicate,
                "required": json.loads(required),
                "observed": json.loads(observed),
                "disposition": disposition,
            }
            digest = hashlib.sha256(
                self._canonical_json(semantic).encode("utf-8")
            ).hexdigest()
            surface_digest = hashlib.sha256(
                self._canonical_json(surface_ids).encode("utf-8")
            ).hexdigest()
            compacted.append(
                StructuredVerifierFinding(
                    finding_id=f"goal-obligation-{digest[:20]}",
                    domain=ConstraintDomain(domain),
                    subject=subject,
                    predicate=ConstraintPredicate(predicate),
                    required=json.loads(required),
                    observed=json.loads(observed),
                    disposition=FindingDisposition(disposition),
                    provenance={
                        "aggregation_basis": (
                            "shared_top_level_import_namespace"
                            if domain == ConstraintDomain.MODULE.value
                            else "shared_goal_predicate"
                        ),
                        "surface_finding_count": len(members),
                        "surface_finding_ids_sha256": surface_digest,
                        "surface_subject_count": len(surface_subjects),
                        "surface_subjects_sample": surface_subjects[:4],
                        "source_file_count": len(source_files),
                        "source_files_sample": source_files[:2],
                    },
                )
            )
        return tuple(compacted)

    def adapt(self, report: StructuredVerifierReport) -> ExecutableVerification:
        compacted = self._group_findings(report.findings)
        grouped_report = replace(
            report,
            findings=compacted,
            details={
                **report.details,
                "constraint_compaction": {
                    "schema": self.schema,
                    "surface_finding_count": len(report.findings),
                    "obligation_group_count": len(compacted),
                    "raw_findings_archived": True,
                    "raw_findings_in_model_view": False,
                },
            },
        )
        outcome = super().adapt(grouped_report)
        if outcome.passed is True:
            return replace(outcome, candidate_assessment=None)
        return outcome
