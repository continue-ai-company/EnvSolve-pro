from __future__ import annotations

import re

from envsolve.solver import CandidateValidation, DeploymentCandidate
from envsolve_harness.scripts.open_program import OpenCandidateProgramValidator


OBSERVABLE_OPEN_PROGRAM_POLICY = "open-candidate-program-v2-observable"
_ENVIRONMENT_MUTATION = re.compile(
    r"""
    \b(?:
        apt(?:-get)?\s+(?:install|update|upgrade)
        |apk\s+(?:add|update|upgrade)
        |(?:brew|dnf|yum)\s+(?:install|update|upgrade)
        |(?:python(?:\d+(?:\.\d+)?)?\s+-m\s+)?pip(?:\d+(?:\.\d+)?)?
            \s+install
        |(?:uv|poetry|pdm)\s+(?:add|install|sync)
        |(?:conda|mamba|micromamba)\s+(?:create|install|update)
        |(?:npm|pnpm|yarn)\s+(?:add|ci|install)
        |(?:python(?:\d+(?:\.\d+)?)?)\s+-m\s+venv
        |pyenv\s+install
        |git\s+submodule\s+update
        |(?:cmake|make|meson|ninja)\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
_NULL_OUTPUT_REDIRECTION = re.compile(
    r"(?:&>>?|[12]?>>?)\s*[\"']?/dev/null[\"']?"
)


def preserve_mutation_diagnostics(script: str) -> tuple[str, tuple[str, ...]]:
    """Remove output-discard redirections only from environment mutation lines."""
    rewritten: list[str] = []
    changed: list[str] = []
    for raw_line in script.splitlines():
        line = raw_line
        if _ENVIRONMENT_MUTATION.search(line) and _NULL_OUTPUT_REDIRECTION.search(line):
            visible = _NULL_OUTPUT_REDIRECTION.sub("", line)
            visible = re.sub(r"[ \t]{2,}", " ", visible).rstrip()
            if visible != line:
                changed.append(line.strip())
                line = visible
        rewritten.append(line)
    return "\n".join(rewritten).rstrip() + "\n", tuple(changed)


class ObservableOpenCandidateProgramValidator(OpenCandidateProgramValidator):
    """Keep open Bash programs while making mutation failures observable."""

    policy_id = OBSERVABLE_OPEN_PROGRAM_POLICY
    prompt_contract = (
        OpenCandidateProgramValidator.prompt_contract
        + """

Every environment mutation or build step must preserve diagnostic output. Do not
redirect installation, environment creation, dependency synchronization, or build
stdout/stderr to `/dev/null`. Quiet flags are allowed, but failures must remain
visible to the next solver turn.
""".rstrip()
    )

    def validate(self, candidate: DeploymentCandidate) -> CandidateValidation:
        base = super().validate(candidate)
        if not base.accepted:
            return base
        normalized, changed = preserve_mutation_diagnostics(
            str(base.normalized_script)
        )
        return CandidateValidation(
            True,
            self.policy_id,
            normalized_script=normalized,
            details={
                **base.details,
                "diagnostic_output_policy": "preserve-environment-mutation-failures",
                "diagnostic_redirections_removed": list(changed),
                "diagnostic_redirection_removal_count": len(changed),
            },
        )
