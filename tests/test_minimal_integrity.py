from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.solver import DeploymentCandidate
from envsolve_harness.integrity.minimal import (
    MinimalIntegrityGoalVerifier,
    inspect_minimal_repository_integrity,
)
from envsolve_harness.scripts.minimal_integrity import MinimalIntegrityCandidateValidator


class MinimalIntegrityTest(unittest.TestCase):
    def test_candidate_contract_declares_dynamic_project_root(self) -> None:
        contract = " ".join(MinimalIntegrityCandidateValidator.prompt_contract.split())

        self.assertIn("current working directory", contract)
        self.assertIn("absolute path is not stable", contract)

    def test_candidate_policy_allows_deployment_artifacts(self) -> None:
        validation = MinimalIntegrityCandidateValidator().validate(
            DeploymentCandidate(
                "candidate",
                "printf 'value = 1\\n' > compatibility.py",
                "materialize a compatibility artifact",
            )
        )

        self.assertTrue(validation.accepted)
        self.assertFalse(validation.details["semantic_rules"])

    def test_repository_audit_allows_untracked_outputs_but_not_tracked_edits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            tracked = root / "tracked.py"
            tracked.write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.py"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            (root / "compatibility.py").write_text("value = 2\n", encoding="utf-8")

            clean = inspect_minimal_repository_integrity(root, revision)
            tracked.write_text("value = 3\n", encoding="utf-8")
            modified = inspect_minimal_repository_integrity(root, revision)

        self.assertTrue(clean.valid)
        self.assertFalse(modified.valid)
        self.assertEqual(modified.tracked_changes, ("tracked.py",))

    def test_goal_verifier_removes_import_provenance_as_a_hard_gate(self) -> None:
        verifier = MinimalIntegrityGoalVerifier(
            ExecutableGoalContract(
                "goal",
                "Require success",
                "printf '{}\\n' > \"$ENVSOLVE_GOAL_REPORT\"",
            )
        )
        command, _, _ = verifier._command(
            DeploymentCandidate("candidate", "true", "test"),
            DockerEnvironmentHandle("container", Path("/tmp/worktree"), "/data/project"),
            "nonce",
        )

        self.assertIn('"performed": false', command)
        self.assertIn("deployment provenance is a measured outcome", command)
        self.assertNotIn("importlib.util.find_spec", command)


if __name__ == "__main__":
    unittest.main()
