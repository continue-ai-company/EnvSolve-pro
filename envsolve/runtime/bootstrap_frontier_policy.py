from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from typing import Any

from envsolve.constraints.bootstrap_frontier import (
    build_model_bootstrap_contradiction_frontier,
)
from envsolve.runtime.goal_frontier_policy import GoalFrontierDeploymentPolicy
from envsolve.solver import DeploymentCandidate
from envsolve.state import EnvironmentState


BOOTSTRAP_FRONTIER_PROFILE = "bootstrap-contradiction-frontier-v2"

BOOTSTRAP_FRONTIER_SYSTEM_PROMPT = """
The state contains a bootstrap_contradiction_frontier derived from prior
candidate execution, before the public goal can run. It makes runtime branches,
build strategies, and repeated failure signatures explicit.

Direct attempt outcomes are observations. A branch marked
search-dominated-by-observed-failures is not logically impossible: it means
that repeated fresh-environment attempts under multiple strategies have not
made the branch productive. Prefer a materially different runtime or dependency
strategy, or add new executable evidence that justifies revisiting it. Do not
repeat an exact failure signature with the same relevant strategy.

Successful bootstrap evidence overrides failure-only search pressure. The
frontier never closes the operation space and never prescribes package names
or commands. Produce one open, complete cumulative Bash program using all
repository and execution evidence.
""".strip()


class BootstrapFrontierDeploymentPolicy(GoalFrontierDeploymentPolicy):
    """Open-program policy over goal and bootstrap contradiction frontiers."""

    def __init__(
        self,
        *args: Any,
        bootstrap_frontier_profile: str = BOOTSTRAP_FRONTIER_PROFILE,
        **kwargs: Any,
    ) -> None:
        if bootstrap_frontier_profile != BOOTSTRAP_FRONTIER_PROFILE:
            raise ValueError("Unsupported bootstrap contradiction frontier profile")
        super().__init__(*args, **kwargs)
        if self.max_feedback_chars < 20_000:
            raise ValueError(
                "Bootstrap-frontier feedback budget must be at least 20000 characters"
            )
        self.bootstrap_frontier_profile = bootstrap_frontier_profile

    def _state_projection(self, state: EnvironmentState) -> dict[str, Any]:
        full_limit = self.max_feedback_chars
        frontier_limit = max(6_000, min(12_000, int(full_limit * 0.20)))
        self.max_feedback_chars = full_limit - frontier_limit - 128
        try:
            projection = super()._state_projection(state)
        finally:
            self.max_feedback_chars = full_limit
        projection["bootstrap_contradiction_frontier"] = (
            build_model_bootstrap_contradiction_frontier(
                state,
                max_chars=frontier_limit,
            )
        )
        if self._json_size(projection) > full_limit:
            raise ValueError(
                "Bootstrap-frontier solver feedback exceeds the model context contract"
            )
        return projection

    def propose(self, state: EnvironmentState) -> DeploymentCandidate:
        original_language = self.candidate_language
        self.candidate_language = "\n\n".join(
            item
            for item in (
                original_language.strip(),
                BOOTSTRAP_FRONTIER_SYSTEM_PROMPT,
            )
            if item
        )
        try:
            candidate = super().propose(state)
        finally:
            self.candidate_language = original_language

        frontier = candidate.metadata["model_input_projection"][
            "bootstrap_contradiction_frontier"
        ]
        encoded = json.dumps(
            frontier,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        metadata = {
            **candidate.metadata,
            "generator": "bootstrap-frontier-model-policy-v2",
            "constraint_profile": BOOTSTRAP_FRONTIER_PROFILE,
            "bootstrap_frontier_profile": BOOTSTRAP_FRONTIER_PROFILE,
            "bootstrap_contradiction_frontier_snapshot": frontier,
            "bootstrap_contradiction_frontier_sha256": hashlib.sha256(
                encoded.encode("utf-8")
            ).hexdigest(),
            "goal_frontier_profile": candidate.metadata.get(
                "goal_frontier_profile"
            ),
        }
        return replace(candidate, metadata=metadata)
