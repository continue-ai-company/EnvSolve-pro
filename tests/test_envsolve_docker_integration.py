from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from envsolve.runtime import DockerFreshEnvironmentProvider, PythonDeploymentVerifier
from envsolve.solver import DeploymentCandidate


@unittest.skipUnless(
    os.environ.get("ENVSOLVE_DOCKER_TEST") == "1",
    "set ENVSOLVE_DOCKER_TEST=1 to run the real Docker boundary test",
)
class EnvSolveDockerIntegrationTest(unittest.TestCase):
    def test_clean_checkout_candidate_verification_and_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "setup.py").write_text(
                "from setuptools import setup\nsetup(name='envsolve-smoke', version='0.0.1')\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "init", "-q"], cwd=source, check=True)
            subprocess.run(
                ["git", "config", "user.email", "envsolve@example.test"],
                cwd=source,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "EnvSolve Test"],
                cwd=source,
                check=True,
            )
            subprocess.run(["git", "add", "setup.py"], cwd=source, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=source, check=True)
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=source,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            provider = DockerFreshEnvironmentProvider(
                source_repository=source,
                worktrees_root=root / "worktrees",
                repository="envsolve/smoke",
                revision=revision,
                image="ghcr.io/jetbrains-research/envbench-python:latest",
            )
            candidate = DeploymentCandidate(
                "candidate-1",
                (
                    "set -euo pipefail\n"
                    "python -m pip install --no-deps --no-build-isolation -e .\n"
                ),
                "Install the synthetic project",
            )
            base_runtime = provider.observe_base_runtime()
            environment = provider.provision(candidate)
            try:
                result = PythonDeploymentVerifier(
                    command_timeout=180, collect_tests=False
                ).verify(candidate, environment)
            finally:
                provider.release(environment)

            self.assertTrue(base_runtime.python_version)
            self.assertEqual(
                base_runtime.image_digest,
                environment.receipt.image_digest,
            )
            self.assertTrue(result.passed, result.bootstrap.stderr)
            self.assertFalse(environment.handle.worktree.exists())


if __name__ == "__main__":
    unittest.main()
