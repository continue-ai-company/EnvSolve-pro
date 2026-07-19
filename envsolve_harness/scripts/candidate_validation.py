from __future__ import annotations

import re

from envsolve.solver import CandidateValidation, DeploymentCandidate
from envsolve_harness.scripts.replay_actions import (
    REPLAY_IR_POLICY,
    ReplayActionKind,
    analyze_successful_command,
)


_VENV_CREATE_PATTERN = re.compile(
    r"^(?:\S*/)?python\d*(?:\.\d+)?\s+-m\s+venv\s+(?P<path>\.venv|venv)$"
)
_VENV_ACTIVATE_PATTERN = re.compile(
    r"^(?:source|\.)\s+(?:\$\{PROJECT_ROOT\}/)?"
    r"(?P<path>\.venv|venv)/bin/activate$"
)


def _venv_path(command: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.fullmatch(command.strip())
    return match.group("path") if match else None


class TypedReplayCandidateValidator:
    """Validate and canonicalize complete deployment programs with frozen replay IR."""

    policy_id = f"complete-candidate-v4+{REPLAY_IR_POLICY}"
    prompt_contract = """\
Write one replayable environment mutation per line. Blank lines, comments, and
an optional shell shebang are ignored. Do not use shell control flow, semicolons,
command substitution, background jobs, file edits, or conditional idempotence
wrappers; every candidate runs in a fresh checkout and container.

Supported mutations are package-index update/install commands for apt, apt-get,
apk, brew, dnf, or yum; Python package install/sync commands using pip,
`python -m pip`, uv, poetry, PDM, conda, mamba, or micromamba; pyenv runtime setup;
safe environment exports; and `.venv` or `venv` activation. A virtual environment
may be created only as `python -m venv .venv`, `python -m venv venv`, or the same
form with a versioned Python executable. Every virtual environment created by the
candidate must be activated after creation so subsequent verification uses the same
runtime. The fail-fast shell prefix is added by the validator, so do not add control
structures around commands. Never export
PYTHONPATH, PYTHONHOME, PYTHONUSERBASE, PYTHONSTARTUP, MYPYPATH, LD_PRELOAD,
LD_LIBRARY_PATH, DYLD_INSERT_LIBRARIES, or DYLD_LIBRARY_PATH.
""".strip()

    def validate(self, candidate: DeploymentCandidate) -> CandidateValidation:
        commands: list[str] = []
        action_count = 0
        created_venvs: dict[str, int] = {}
        activated_venvs: dict[str, list[int]] = {}
        for raw_line in candidate.script.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line in {"set -e", "set -eu", "set -euo pipefail"}:
                continue
            if line == 'PROJECT_ROOT="$(pwd)"':
                commands.append(line)
                continue
            analysis = analyze_successful_command(line)
            if analysis.unsupported_reason:
                return CandidateValidation(
                    False,
                    self.policy_id,
                    reason=f"unsupported candidate command: {analysis.unsupported_reason}",
                    details={"command": line},
                )
            if analysis.dropped or not analysis.actions:
                return CandidateValidation(
                    False,
                    self.policy_id,
                    reason="complete candidates cannot contain observation-only commands",
                    details={"command": line},
                )
            for action in analysis.actions:
                action_index = action_count
                commands.append(action.command)
                action_count += 1
                if action.kind == ReplayActionKind.VIRTUAL_ENVIRONMENT_CREATE.value:
                    path = _venv_path(action.command, _VENV_CREATE_PATTERN)
                    if path is None:
                        return CandidateValidation(
                            False,
                            self.policy_id,
                            reason="virtual environment must be created at the project root",
                            details={"command": action.command},
                        )
                    created_venvs[path] = action_index
                elif action.kind == ReplayActionKind.ENVIRONMENT_ACTIVATE.value:
                    path = _venv_path(action.command, _VENV_ACTIVATE_PATTERN)
                    if path is None:
                        return CandidateValidation(
                            False,
                            self.policy_id,
                            reason="virtual environment activation must resolve from the project root",
                            details={"command": action.command},
                        )
                    activated_venvs.setdefault(path, []).append(action_index)
        if not action_count:
            return CandidateValidation(
                False,
                self.policy_id,
                reason="candidate contains no replayable environment mutation",
            )
        for path, create_index in created_venvs.items():
            if not any(
                activate_index > create_index
                for activate_index in activated_venvs.get(path, ())
            ):
                return CandidateValidation(
                    False,
                    self.policy_id,
                    reason=(
                        f"created virtual environment {path} must be activated "
                        "after creation"
                    ),
                    details={"virtual_environment": path},
                )
        normalized = "set -euo pipefail\n" + "\n".join(dict.fromkeys(commands)) + "\n"
        return CandidateValidation(
            True,
            self.policy_id,
            normalized_script=normalized,
            details={"action_count": action_count},
        )
