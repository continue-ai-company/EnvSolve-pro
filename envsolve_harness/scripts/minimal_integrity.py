from __future__ import annotations

from envsolve.solver import CandidateValidation, DeploymentCandidate


MINIMAL_INTEGRITY_POLICY = "minimal-evaluator-integrity-v1"


class MinimalIntegrityCandidateValidator:
    """Check transport invariants without deciding deployment semantics."""

    policy_id = MINIMAL_INTEGRITY_POLICY
    _base_prompt_contract = """\
Return one complete, self-contained Bash program that can be sourced from the
project root in a fresh benchmark container. The project root is the current
working directory when the program starts; its absolute path is not stable across
construction, replay, and evaluation. Do not terminate or replace the controlling
shell with `exit`, `return`, or `exec`. Do not modify tracked source, tests,
dependency declarations, lockfiles, type-checker configuration, or benchmark-owned
state. You may create ordinary environment, build, cache, and compatibility
artifacts when they are part of the deployment itself. Do not manually place
placeholder import providers in `site-packages`; install a distribution or use an
auditable repository provider. The trusted goal and official evaluator remain
outside your control. You may change directories temporarily, but the program must
return the controlling shell to its starting project root before it finishes.
""".strip()
    prompt_contract = _base_prompt_contract

    def __init__(
        self,
        max_chars: int = 100_000,
        *,
        protect_evaluator_artifacts: bool = False,
    ) -> None:
        if max_chars <= 0:
            raise ValueError("Candidate size bound must be positive")
        self.max_chars = max_chars
        self.protect_evaluator_artifacts = protect_evaluator_artifacts
        self.policy_id = (
            "minimal-evaluator-integrity-v2"
            if protect_evaluator_artifacts
            else MINIMAL_INTEGRITY_POLICY
        )
        self.prompt_contract = self._base_prompt_contract
        if protect_evaluator_artifacts:
            self.prompt_contract += """

Do not create tracked or untracked evaluator configuration, including
`pyrightconfig.json`, or type-only `.pyi` providers. Install or configure a real
runtime provider instead. The final replay and live compatibility observations
audit these evaluator-only artifacts independently of whether the public goal passes.
"""

    def validate(self, candidate: DeploymentCandidate) -> CandidateValidation:
        script = candidate.script.replace("\r\n", "\n").replace("\r", "\n")
        if "\x00" in script:
            return CandidateValidation(
                False,
                self.policy_id,
                reason="candidate program contains a NUL byte",
            )
        normalized = script.rstrip() + "\n"
        if len(normalized) > self.max_chars:
            return CandidateValidation(
                False,
                self.policy_id,
                reason="candidate program exceeds the fixed size bound",
                details={
                    "max_chars": self.max_chars,
                    "observed_chars": len(normalized),
                },
            )
        if not any(
            line.strip() and not line.lstrip().startswith("#")
            for line in script.splitlines()
        ):
            return CandidateValidation(
                False,
                self.policy_id,
                reason="candidate program contains no executable shell statement",
            )
        return CandidateValidation(
            True,
            self.policy_id,
            normalized_script=normalized,
            details={
                "script_chars": len(normalized),
                "semantic_rules": False,
                "enforcement": "fresh-replay+trusted-goal+minimal-effect-audit",
            },
        )
