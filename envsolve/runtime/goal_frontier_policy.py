from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from typing import Any

from envsolve.constraints.goal_frontier import (
    MODEL_GOAL_OBLIGATION_FRONTIER_SCHEMA,
    build_model_goal_obligation_frontier,
    ordered_active_goal_findings,
)
from envsolve.runtime.policy import StructuredModelDeploymentPolicy
from envsolve.solver import DeploymentCandidate
from envsolve.state import EnvironmentState


GOAL_FRONTIER_PROFILE = "goal-obligation-frontier-v1"

GOAL_FRONTIER_SYSTEM_PROMPT = """
The state contains a goal_obligation_frontier derived from the latest public
executable-goal report. It groups repeated findings by unresolved top-level
import namespace while preserving source roles and representative paths.
Every group remains part of the goal, including test, documentation, example,
and generated-source findings; source roles organize evidence and do not waive
obligations. Surface counts are amplification, not independent root causes.

A namespace is not necessarily an installable distribution. The frontier does
not prescribe an action: use repository evidence and execution feedback to
decide whether a group requires a declared extra, a distribution, generated
artifacts, a repository-local path, a runtime change, or another valid
environment operation. Produce one open, complete cumulative Bash program.
""".strip()


class GoalFrontierDeploymentPolicy(StructuredModelDeploymentPolicy):
    """Open-program policy over a compressed executable-goal frontier."""

    def __init__(
        self,
        *args: Any,
        goal_frontier_profile: str = GOAL_FRONTIER_PROFILE,
        operation_profile: str = "free-form",
        constraint_profile: str = "flat",
        **kwargs: Any,
    ) -> None:
        if goal_frontier_profile != GOAL_FRONTIER_PROFILE:
            raise ValueError("Unsupported goal-obligation frontier profile")
        if operation_profile != "free-form":
            raise ValueError(
                "Goal-frontier policy preserves an open operation interface"
            )
        if constraint_profile != "flat":
            raise ValueError(
                "Goal-frontier policy replaces only the flat module projection"
            )
        super().__init__(
            *args,
            operation_profile="free-form",
            constraint_profile="flat",
            **kwargs,
        )
        if self.max_feedback_chars < 12_000:
            raise ValueError(
                "Goal-frontier feedback budget must be at least 12000 characters"
            )
        self.goal_frontier_profile = goal_frontier_profile

    @classmethod
    def _verification_view(
        cls,
        item: dict[str, Any],
        *,
        diagnostic_limit: int = 4_000,
        include_environment_provenance: bool = False,
    ) -> dict[str, Any]:
        view = super()._verification_view(
            item,
            diagnostic_limit=diagnostic_limit,
            include_environment_provenance=include_environment_provenance,
        )
        diagnostic = view.get("diagnostic")
        if not isinstance(diagnostic, dict):
            return view
        diagnostic = json.loads(json.dumps(diagnostic, ensure_ascii=True))
        report_details = diagnostic.get("report_details")
        report = (
            report_details.get("goal_report")
            if isinstance(report_details, dict)
            else None
        )
        findings = report.get("findings") if isinstance(report, dict) else None
        if isinstance(findings, list):
            report["findings"] = {
                "count": len(findings),
                "omitted_from_raw_feedback": True,
                "projected_as": MODEL_GOAL_OBLIGATION_FRONTIER_SCHEMA,
            }
        view["diagnostic"] = diagnostic
        return view

    def _repository_evidence_view(
        self,
        state: EnvironmentState,
        *,
        max_chars: int,
    ) -> dict[str, Any] | None:
        if self._repository_evidence_index is None:
            return None
        findings = ordered_active_goal_findings(state)
        if not findings:
            return None
        return self._repository_evidence_index.retrieve(
            findings,
            max_chars=max_chars,
        )

    def _state_projection(self, state: EnvironmentState) -> dict[str, Any]:
        full_limit = self.max_feedback_chars
        frontier_limit = max(4_096, min(16_000, int(full_limit * 0.25)))
        self.max_feedback_chars = full_limit - frontier_limit - 128
        try:
            projection = super()._state_projection(state)
        finally:
            self.max_feedback_chars = full_limit

        projection.pop("active_module_requirements", None)
        projection["constraint_conflicts"] = self._constraint_view(
            state,
            compact_module_surfaces=True,
        )
        projection["goal_obligation_frontier"] = (
            build_model_goal_obligation_frontier(
                state,
                max_chars=frontier_limit,
            )
        )
        if self._json_size(projection) > full_limit:
            raise ValueError(
                "Goal-frontier solver feedback exceeds the model context contract"
            )
        return projection

    def propose(self, state: EnvironmentState) -> DeploymentCandidate:
        original_language = self.candidate_language
        self.candidate_language = "\n\n".join(
            item
            for item in (original_language.strip(), GOAL_FRONTIER_SYSTEM_PROMPT)
            if item
        )
        try:
            candidate = super().propose(state)
        finally:
            self.candidate_language = original_language

        frontier = candidate.metadata["model_input_projection"][
            "goal_obligation_frontier"
        ]
        encoded = json.dumps(
            frontier,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        metadata = {
            **candidate.metadata,
            "generator": "goal-frontier-model-policy-v1",
            "base_constraint_profile": "flat",
            "constraint_profile": GOAL_FRONTIER_PROFILE,
            "goal_frontier_profile": GOAL_FRONTIER_PROFILE,
            "goal_obligation_frontier_snapshot": frontier,
            "goal_obligation_frontier_sha256": hashlib.sha256(
                encoded.encode("utf-8")
            ).hexdigest(),
        }
        return replace(candidate, metadata=metadata)
