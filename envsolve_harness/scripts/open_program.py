from __future__ import annotations

from envsolve.solver import CandidateValidation, DeploymentCandidate


OPEN_PROGRAM_POLICY = "open-candidate-program-v1"


class OpenCandidateProgramValidator:
    """Admit complete shell programs; execution effects determine validity."""

    policy_id = OPEN_PROGRAM_POLICY
    prompt_contract = """\
Return one complete, self-contained Bash program that will be sourced from the
project root in a fresh container. You may use normal Bash composition and control
flow. Do not edit tracked repository files, inject importable source files, suppress
the terminal verifier, or delete evaluator-owned workspace artifacts. The program
must leave the selected Python environment active for commands that run after it.

Shell syntax is not restricted to a command schema. Safety and correctness are
decided by isolated execution, repository-effect audit, and executable postconditions.
""".strip()

    def __init__(self, max_chars: int = 100_000) -> None:
        if max_chars <= 0:
            raise ValueError("Open candidate size bound must be positive")
        self.max_chars = max_chars

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
        executable_lines = [
            line
            for line in script.splitlines()
            if line.strip()
            and not line.lstrip().startswith("#")
        ]
        if not executable_lines:
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
                "interface": OPEN_PROGRAM_POLICY,
                "script_chars": len(normalized),
                "safety_boundary": "fresh-container+effect-audit+postconditions",
            },
        )
