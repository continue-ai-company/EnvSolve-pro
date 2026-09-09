from __future__ import annotations

import subprocess

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.solver import DeploymentCandidate
from envsolve_harness.progress_replay import (
    ACTIVE_PYTHON_MARKER,
    PythonConditionVerifier,
    compact_replay_feedback,
    replay_evidence,
)


def verifier() -> PythonConditionVerifier:
    return PythonConditionVerifier(
        ExecutableGoalContract("goal", "fixture", "true"),
        required_python="3.10",
    )


def test_condition_check_runs_after_candidate_in_the_same_shell() -> None:
    candidate = DeploymentCandidate("candidate", "source .venv/bin/activate", "test")
    handle = DockerEnvironmentHandle("container", None, "/data/project")

    command, completion, _ = verifier()._command(candidate, handle, "nonce")

    assert command.index("source .venv/bin/activate") < command.index(
        "ENVSOLVE_PROGRESS_ACTIVE_PYTHON=$("
    )
    assert command.index(ACTIVE_PYTHON_MARKER) < command.index(completion)
    assert "required Python %s, observed %s" in command


def test_replay_evidence_records_observed_interpreter_and_failure_tail() -> None:
    replay = {
        "status": "fail",
        "verification": {
            "summary": "candidate failed",
            "bootstrap": {
                "exit_code": 42,
                "duration_seconds": 9.5,
                "stdout": f"setup\n{ACTIVE_PYTHON_MARKER}3.11.9\n",
                "stderr": "required Python 3.10, observed 3.11.9",
            },
        },
    }

    evidence = replay_evidence(replay, source="preflight")

    assert evidence.status == "fail"
    assert evidence.observed_python == "3.11.9"
    assert evidence.public_goal_passed is None
    assert "required Python 3.10" in (evidence.failure_summary or "")
    assert "observed_python=3.11.9" in compact_replay_feedback(replay)


def test_successful_replay_maps_to_passing_evidence() -> None:
    replay = {
        "status": "pass",
        "verification": {
            "bootstrap": {
                "exit_code": 0,
                "duration_seconds": 1,
                "stdout": f"{ACTIVE_PYTHON_MARKER}3.10.14\n",
                "stderr": "",
            }
        },
    }

    evidence = replay_evidence(replay, source="qualification")

    assert evidence.public_goal_passed is True
    assert evidence.observed_python == "3.10.14"
    assert evidence.failure_summary is None


def test_condition_command_accepts_required_major_minor() -> None:
    candidate = DeploymentCandidate("candidate", "true", "test")
    handle = DockerEnvironmentHandle("container", None, "/data/project")
    command, _, _ = verifier()._command(candidate, handle, "nonce")
    start = command.index("ENVSOLVE_PROGRESS_ACTIVE_PYTHON=$(")
    stop = command.index("printf '%s\\n' ENVSOLVE_GOAL_CANDIDATE_COMPLETED", start)
    condition = command[start:stop]

    process = subprocess.run(
        ["/bin/bash", "-lc", condition],
        capture_output=True,
        text=True,
        check=False,
    )

    expected = 0 if process.stdout.strip().endswith(("3.10", "3.10.14")) else 42
    assert process.returncode == expected
