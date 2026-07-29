from __future__ import annotations

from pathlib import Path

from envsolve.runtime import ExecutableGoalContract
from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.stateful_goal_verifier_v22 import (
    StatefulExecutableGoalVerifierV22,
)
from envsolve.runtime.stateful_integrity_v22 import (
    python_module_identity_audit_command,
)
from envsolve.solver import DeploymentCandidate


def test_v22_audit_composes_source_and_module_identity_provenance() -> None:
    command = python_module_identity_audit_command("/data/project")

    assert "python-import-source-provenance-v2" in command
    assert "python-module-identity-provenance-v2.2" in command
    assert "project source acquired an undeclared module identity" in command


def test_v22_keeps_initial_observation_outside_candidate_identity_audit() -> None:
    verifier = StatefulExecutableGoalVerifierV22(
        ExecutableGoalContract(
            contract_id="goal",
            description="Goal",
            program="true",
        )
    )
    handle = DockerEnvironmentHandle(
        container_id="container",
        worktree=Path("/tmp/project"),
        container_workdir="/data/project",
    )
    probe, _, _ = verifier._command(
        DeploymentCandidate(
            "probe",
            ":",
            "Initial observation",
            metadata={"execution_role": "initial-observation"},
        ),
        handle,
        "probe-nonce",
    )
    candidate, _, _ = verifier._command(
        DeploymentCandidate("candidate", "true", "Candidate"),
        handle,
        "candidate-nonce",
    )

    assert "python-module-identity-provenance-v2.2" not in probe
    assert "python-module-identity-provenance-v2.2" in candidate
