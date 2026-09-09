from __future__ import annotations

import re
import shlex
from typing import Any

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.solver import DeploymentCandidate
from envsolve_harness.boundary_v6 import (
    BoundaryV6OfficialAlignedExecutableGoalVerifier,
)
from envsolve_harness.progress_state import ExecutionEvidence


ACTIVE_PYTHON_MARKER = "ENVSOLVE_PROGRESS_ACTIVE_PYTHON_V1="
_OBSERVED_PYTHON = re.compile(
    rf"^{re.escape(ACTIVE_PYTHON_MARKER)}(?P<version>[^\r\n]+)$",
    re.MULTILINE,
)


class PythonConditionVerifier(BoundaryV6OfficialAlignedExecutableGoalVerifier):
    """Observe a requested Python version without changing the public goal."""

    check_profile = "envsolve-progress-python-condition-v1"

    def __init__(self, *args: Any, required_python: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.required_python = required_python.strip()
        if not self.required_python:
            raise ValueError("required Python version cannot be empty")

    def _command(
        self,
        candidate: DeploymentCandidate,
        handle: DockerEnvironmentHandle,
        nonce: str,
    ) -> tuple[str, str, str]:
        command, completion_marker, report_begin = super()._command(
            candidate,
            handle,
            nonce,
        )
        marker_line = f"printf '%s\\n' {shlex.quote(completion_marker)}"
        if command.count(marker_line) != 1:
            raise RuntimeError("cannot place the Python condition observation")
        required = shlex.quote(self.required_python)
        condition = "\n".join(
            (
                "ENVSOLVE_PROGRESS_ACTIVE_PYTHON=$(command python -c "
                "'import platform; print(platform.python_version())')",
                (
                    f"printf '{ACTIVE_PYTHON_MARKER}%s\\n' "
                    '"$ENVSOLVE_PROGRESS_ACTIVE_PYTHON"'
                ),
                (
                    'case "$ENVSOLVE_PROGRESS_ACTIVE_PYTHON" in '
                    f"{required}|{required}.*) ;;"
                ),
                (
                    "*) printf 'required Python %s, observed %s\\n' "
                    f"{required} \"$ENVSOLVE_PROGRESS_ACTIVE_PYTHON\" >&2; exit 42 ;;"
                ),
                "esac",
            )
        )
        return (
            command.replace(marker_line, f"{condition}\n{marker_line}", 1),
            completion_marker,
            report_begin,
        )


def observed_python(replay: dict[str, Any]) -> str | None:
    verification = replay.get("verification")
    if not isinstance(verification, dict):
        return None
    bootstrap = verification.get("bootstrap")
    if not isinstance(bootstrap, dict):
        return None
    match = _OBSERVED_PYTHON.search(str(bootstrap.get("stdout") or ""))
    return match.group("version").strip() if match is not None else None


def replay_evidence(
    replay: dict[str, Any],
    *,
    source: str,
) -> ExecutionEvidence:
    status = replay.get("status")
    normalized_status = (
        status
        if status in {"pass", "fail", "unknown", "infrastructure_error"}
        else "unknown"
    )
    verification = replay.get("verification")
    verification = verification if isinstance(verification, dict) else {}
    bootstrap = verification.get("bootstrap")
    bootstrap = bootstrap if isinstance(bootstrap, dict) else {}
    exit_code = bootstrap.get("exit_code")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        exit_code = None
    duration = bootstrap.get("duration_seconds")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        duration = None
    public_goal_passed = (
        True
        if normalized_status == "pass"
        else False
        if normalized_status == "fail" and exit_code == 0
        else None
    )
    failure = None
    if normalized_status != "pass":
        parts = [
            str(replay.get("infrastructure_error") or "").strip(),
            str(verification.get("summary") or "").strip(),
            _tail(str(bootstrap.get("stderr") or "")),
            _tail(str(bootstrap.get("stdout") or "")),
        ]
        failure = "\n".join(part for part in parts if part) or normalized_status
    return ExecutionEvidence(
        status=normalized_status,
        source=source,
        bootstrap_exit_code=exit_code,
        public_goal_passed=public_goal_passed,
        observed_python=observed_python(replay),
        duration_seconds=float(duration) if duration is not None else None,
        failure_summary=failure,
    )


def compact_replay_feedback(replay: dict[str, Any]) -> str:
    evidence = replay_evidence(replay, source="clean-replay")
    lines = [
        f"status={evidence.status}",
        f"bootstrap_exit_code={evidence.bootstrap_exit_code}",
        f"public_goal_passed={evidence.public_goal_passed}",
        f"observed_python={evidence.observed_python}",
    ]
    if evidence.failure_summary:
        lines.extend(("failure_evidence:", evidence.failure_summary))
    return "\n".join(lines)


def _tail(value: str, limit: int = 4000) -> str:
    stripped = value.strip()
    return stripped[-limit:] if stripped else ""
