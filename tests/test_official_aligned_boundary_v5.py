from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from envsolve.runtime.docker import DockerFreshEnvironmentProvider
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.solver import DeploymentCandidate
from envsolve_harness.boundary_v5 import (
    BoundaryV5OfficialAlignedExecutableGoalVerifier,
)
from envsolve_harness.integrity.repository import inspect_repository


@unittest.skipUnless(
    os.environ.get("ENVSOLVE_MINIMAL_B_DOCKER_TEST") == "1",
    "set ENVSOLVE_MINIMAL_B_DOCKER_TEST=1 to run clean replay integration",
)
class OfficialAlignedBoundaryV5IntegrationTest(unittest.TestCase):
    def test_allows_install_but_rejects_repo_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repository"
            repository.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repository,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=repository,
                check=True,
            )
            (repository / "README.md").write_text("original\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "initial"],
                cwd=repository,
                check=True,
            )
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repository,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            report = json.dumps(
                {
                    "schema": "envsolve-goal-report-v1",
                    "status": "pass",
                    "finding_set_complete": True,
                    "findings": [],
                    "details": {},
                },
                separators=(",", ":"),
            )
            contract = ExecutableGoalContract(
                "official-aligned-test",
                "Accept an ordinary dependency installation",
                f"printf '%s\\n' {shlex.quote(report)} > \"$ENVSOLVE_GOAL_REPORT\"",
            )
            provider = DockerFreshEnvironmentProvider(
                source_repository=repository,
                worktrees_root=root / "worktrees",
                repository="owner/repo",
                revision=revision,
                image="ghcr.io/jetbrains-research/envbench-python:latest",
                create_timeout=300,
            )
            verifier = BoundaryV5OfficialAlignedExecutableGoalVerifier(
                contract,
                observation_timeout=120,
                effect_auditor=lambda worktree: inspect_repository(
                    worktree,
                    revision,
                ),
            )
            install = DeploymentCandidate(
                "install",
                """\
shim_dir=$(mktemp -d)
cat > "$shim_dir/setup.py" <<'PY'
from setuptools import setup
setup(name="synthetic-dependency", version="0", py_modules=[])
PY
python -m pip install "$shim_dir"
""",
                "install an ordinary dependency outside the repository",
            )
            mutation = DeploymentCandidate(
                "mutation",
                "printf 'changed\\n' > README.md",
                "exercise repository integrity",
            )

            installed_environment = provider.provision(install)
            try:
                installed = verifier.verify(install, installed_environment)
            finally:
                provider.release(installed_environment)
            mutated_environment = provider.provision(mutation)
            try:
                mutated = verifier.verify(mutation, mutated_environment)
            finally:
                provider.release(mutated_environment)

            self.assertTrue(installed.passed, installed)
            self.assertFalse(mutated.passed, mutated)
            self.assertIn("effect boundaries", mutated.summary.lower())


if __name__ == "__main__":
    unittest.main()
