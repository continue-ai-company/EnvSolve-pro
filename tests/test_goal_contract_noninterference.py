from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

from envsolve.runtime.docker import (
    DockerEnvironmentHandle,
    DockerFreshEnvironmentProvider,
)
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.solver import (
    DeploymentCandidate,
    EnvironmentReceipt,
    ProvisionedEnvironment,
)
from envsolve_harness.boundary_v2 import (
    BoundaryV2MinimalBExecutableGoalVerifier,
    NonInterferingExecutableGoalVerifier,
)
from envsolve_harness.integrity.repository import inspect_repository


class GoalContractNoninterferenceTest(unittest.TestCase):
    def test_candidate_python_function_cannot_intercept_trusted_goal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outer = Path(directory)
            project = outer / "project"
            binary = project / ".trusted-bin"
            binary.mkdir(parents=True)
            (binary / "python").symlink_to(sys.executable)

            contract = ExecutableGoalContract(
                contract_id="noninterference-fixture-v1",
                description="The real interpreter must report one finding.",
                program="""\
python - "$ENVSOLVE_GOAL_REPORT" <<'PY'
import json
from pathlib import Path
import sys

Path(sys.argv[1]).write_text(
    json.dumps(
        {
            "schema": "envsolve-goal-report-v1",
            "status": "fail",
            "finding_set_complete": True,
            "findings": [
                {
                    "finding_id": "real-interpreter-finding",
                    "domain": "module",
                    "subject": "real_dependency",
                    "predicate": "present",
                    "required": True,
                    "observed": False,
                    "provenance": {"source": "trusted-child-shell"},
                }
            ],
            "details": {},
        },
        sort_keys=True,
    ),
    encoding="utf-8",
)
PY
""",
            )
            candidate = DeploymentCandidate(
                "candidate-shell-function",
                (
                    f"export PATH={binary}:$PATH\n"
                    "python() {\n"
                    "  printf 'ENVSOLVE_TEST_HIJACKED=1\\n'\n"
                    "  printf '%s\\n' "
                    "'{\"schema\":\"envsolve-goal-report-v1\",'"
                    "'\"status\":\"pass\",\"finding_set_complete\":true,'"
                    "'\"findings\":[],\"details\":{}}' > \"${@: -1}\"\n"
                    "}\n"
                    "export -f python\n"
                ),
                "Try to intercept the trusted interpreter call",
            )
            environment = ProvisionedEnvironment(
                EnvironmentReceipt(
                    "container-1",
                    "fixture-provider",
                    "sha256:image",
                    "owner/repo",
                    "a" * 40,
                    "2026-08-06T00:00:00+00:00",
                ),
                DockerEnvironmentHandle(
                    "container-1",
                    project,
                    str(project),
                ),
            )

            def run_locally(command: list[str], **kwargs: object):
                return subprocess.run(
                    ["/bin/bash", "-c", command[-1]],
                    cwd=project,
                    env=os.environ.copy(),
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=10,
                )

            result = NonInterferingExecutableGoalVerifier(
                contract,
                run_command=run_locally,
            ).verify(candidate, environment)

            self.assertIs(result.passed, False, vars(result))
            self.assertNotIn("ENVSOLVE_TEST_HIJACKED=1", result.bootstrap.stdout)
            self.assertIn("real_dependency", repr(result))


@unittest.skipUnless(
    os.environ.get("ENVSOLVE_DOCKER_TEST") == "1",
    "set ENVSOLVE_DOCKER_TEST=1 to run the real Docker boundary test",
)
class GoalContractDockerNoninterferenceTest(unittest.TestCase):
    def test_exported_python_function_cannot_forge_goal_in_real_container(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "README.md").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=source, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.test"],
                cwd=source,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=source,
                check=True,
            )
            subprocess.run(["git", "add", "."], cwd=source, check=True)
            subprocess.run(
                ["git", "commit", "-qm", "fixture"],
                cwd=source,
                check=True,
            )
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=source,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            image = os.environ.get(
                "ENVSOLVE_DOCKER_IMAGE",
                "ghcr.io/jetbrains-research/envbench-python:latest",
            )
            provider = DockerFreshEnvironmentProvider(
                source_repository=source,
                worktrees_root=root / "worktrees",
                repository="envsolve/noninterference-fixture",
                revision=revision,
                image=image,
            )
            contract = ExecutableGoalContract(
                contract_id="docker-noninterference-fixture-v1",
                description="The real interpreter must report one finding.",
                program="""\
python - "$ENVSOLVE_GOAL_REPORT" <<'PY'
import json
from pathlib import Path
import sys

Path(sys.argv[1]).write_text(
    json.dumps(
        {
            "schema": "envsolve-goal-report-v1",
            "status": "fail",
            "finding_set_complete": True,
            "findings": [
                {
                    "finding_id": "real-container-finding",
                    "domain": "module",
                    "subject": "real_container_dependency",
                    "predicate": "present",
                    "required": True,
                    "observed": False,
                    "provenance": {"source": "trusted-child-shell"},
                }
            ],
            "details": {},
        },
        sort_keys=True,
    ),
    encoding="utf-8",
)
PY
""",
            )
            candidate = DeploymentCandidate(
                "candidate-exported-function",
                (
                    "python() {\n"
                    "  printf '%s\\n' "
                    "'{\"schema\":\"envsolve-goal-report-v1\",'"
                    "'\"status\":\"pass\",\"finding_set_complete\":true,'"
                    "'\"findings\":[],\"details\":{}}' > \"${@: -1}\"\n"
                    "}\n"
                    "export -f python\n"
                ),
                "Try to forge the trusted goal report",
            )
            environment = provider.provision(candidate)
            try:
                result = BoundaryV2MinimalBExecutableGoalVerifier(
                    contract,
                    observation_timeout=180,
                    effect_auditor=lambda worktree: inspect_repository(
                        worktree,
                        revision,
                    ),
                ).verify(candidate, environment)
            finally:
                provider.release(environment)

            self.assertIs(result.passed, False, vars(result))
            self.assertIn("real_container_dependency", repr(result))


if __name__ == "__main__":
    unittest.main()
