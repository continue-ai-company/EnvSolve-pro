from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.runtime.goal_verifier import ExecutableGoalContractVerifier
from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.solver import (
    DeploymentCandidate,
    EnvironmentReceipt,
    ProvisionedEnvironment,
)
from envsolve_harness.integrity.delivery import (
    DeliveryIntegrityGoalVerifier,
    FinalWorkingDirectoryPostconditionMixin,
)


class _ShellDeliveryVerifier(
    FinalWorkingDirectoryPostconditionMixin,
    ExecutableGoalContractVerifier,
):
    check_profile = "test-delivery-integrity-v1"


class DeliveryIntegrityGoalVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.worktree = Path(self.temp.name) / "project"
        self.worktree.mkdir()
        self.test_bin = self.worktree / ".test-bin"
        self.test_bin.mkdir()
        (self.test_bin / "python").symlink_to(Path(sys.executable).resolve())
        self.environment = ProvisionedEnvironment(
            EnvironmentReceipt(
                environment_id="environment-1",
                provider_id="docker",
                image_digest="sha256:image",
                repository="owner/repo",
                revision="abc123",
                created_at="2026-08-31T00:00:00Z",
            ),
            DockerEnvironmentHandle(
                container_id="container-1",
                worktree=self.worktree,
                container_workdir=str(self.worktree),
            ),
        )
        self.contract = ExecutableGoalContract(
            contract_id="delivery-test",
            description="Exercise delivery integrity",
            program=(
                "printf '%s' "
                "'{\"schema\":\"envsolve-goal-report-v1\","
                "\"status\":\"pass\",\"findings\":[]}' "
                '> "$ENVSOLVE_GOAL_REPORT"'
            ),
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _verifier(self) -> _ShellDeliveryVerifier:
        def run_command(
            command: list[str],
            **kwargs: object,
        ) -> subprocess.CompletedProcess[str]:
            env = dict(os.environ)
            env["PATH"] = f"{self.test_bin}{os.pathsep}{env['PATH']}"
            return subprocess.run(
                ["/bin/bash", "-lc", command[-1]],
                cwd=self.worktree,
                env=env,
                **kwargs,
            )

        return _ShellDeliveryVerifier(self.contract, run_command=run_command)

    def test_rejects_candidate_that_leaves_project_root(self) -> None:
        result = self._verifier().verify(
            DeploymentCandidate("candidate-wrong-cwd", "cd /tmp", "Leave root"),
            self.environment,
        )

        self.assertFalse(result.passed)
        self.assertIn("return to the project root", result.summary)
        self.assertEqual(
            Path(result.details["working_directory_violation"]["actual_path"]),
            Path("/tmp").resolve(),
        )

    def test_allows_temporary_directory_change(self) -> None:
        result = self._verifier().verify(
            DeploymentCandidate(
                "candidate-restored-cwd",
                'PROJECT_ROOT=$PWD\ncd /tmp\ncd "$PROJECT_ROOT"',
                "Restore root",
            ),
            self.environment,
        )

        self.assertTrue(result.passed, result.bootstrap.stderr)

    def test_minimal_integrity_variant_instruments_before_completion(self) -> None:
        verifier = DeliveryIntegrityGoalVerifier(self.contract)
        command, completion_marker, _ = verifier._command(
            DeploymentCandidate("candidate", "printf 'candidate-step\\n'", "Test"),
            self.environment.handle,
            "nonce",
        )

        self.assertEqual(
            command.count("ENVSOLVE_GOAL_WORKING_DIRECTORY_VIOLATION_V1="),
            1,
        )
        self.assertLess(
            command.index("ENVSOLVE_GOAL_WORKING_DIRECTORY_VIOLATION_V1="),
            command.index(completion_marker),
        )

    def test_preserves_valid_goal_report(self) -> None:
        result = self._verifier().verify(
            DeploymentCandidate("candidate-stable-cwd", "true", "Stay in root"),
            self.environment,
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.check_profile, "test-delivery-integrity-v1")
