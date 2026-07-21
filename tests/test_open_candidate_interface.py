from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
import unittest

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.verifier import PythonDeploymentVerifier
from envsolve.runtime.workspace import WorkspacePrecondition
from envsolve.solver import (
    DeploymentCandidate,
    EnvironmentReceipt,
    ProvisionedEnvironment,
)
from envsolve_harness.integrity.repository import inspect_repository
from envsolve_harness.scripts.envbench_trajectory import compile_envbench_open_program
from envsolve_harness.scripts.open_program import OpenCandidateProgramValidator
from envsolve_harness.scripts.repo2run import compile_repo2run_open_program


@dataclass(frozen=True)
class _AuditReport:
    valid: bool

    def to_dict(self) -> dict[str, object]:
        return {"valid": self.valid, "policy": "fixture-effect-audit"}


class OpenCandidateInterfaceTest(unittest.TestCase):
    def test_open_validator_admits_shell_composition_but_keeps_hard_bounds(self) -> None:
        validator = OpenCandidateProgramValidator(max_chars=200)
        accepted = validator.validate(
            DeploymentCandidate(
                "candidate-1",
                "rm -rf .venv && python3.10 -m venv .venv\n"
                "source .venv/bin/activate\n"
                "mkdir -p package/_static/assets\n",
                "Replace the environment and materialize generated assets",
            )
        )
        nul = validator.validate(
            DeploymentCandidate("candidate-2", "printf 'x\x00y'\n", "Invalid byte")
        )
        comments = validator.validate(
            DeploymentCandidate("candidate-3", "#!/bin/bash\n# no operation\n", "Empty")
        )
        normalized_overflow = OpenCandidateProgramValidator(max_chars=4).validate(
            DeploymentCandidate("candidate-4", "true", "Normalized size is five")
        )

        self.assertTrue(accepted.accepted)
        self.assertIn("rm -rf .venv &&", accepted.normalized_script)
        self.assertIn("mkdir -p", accepted.normalized_script)
        self.assertFalse(nul.accepted)
        self.assertFalse(comments.accepted)
        self.assertFalse(normalized_overflow.accepted)

    def test_envbench_open_compiler_preserves_order_and_existing_quotes(self) -> None:
        project = "owner__repo@abc"
        result = compile_envbench_open_program(
            [
                {
                    "command": f'cd "/data/project/{project}" && mkdir -p assets',
                    "exit_code": 0,
                },
                {
                    "command": "rm -rf .venv && python3.10 -m venv .venv",
                    "exit_code": 0,
                },
                {"command": "python -m pytest", "exit_code": 1},
                {"command": "python -c 'print(1)'", "exit_code": 0},
            ],
            project_directory=project,
        )

        self.assertEqual(result.unknown_commands, ())
        self.assertIn('cd "${PROJECT_ROOT}" && mkdir -p assets', result.script)
        self.assertNotIn('""${PROJECT_ROOT}""', result.script)
        self.assertLess(
            result.script.index("rm -rf .venv"),
            result.script.index("python -c 'print(1)'"),
        )
        self.assertNotIn("python -m pytest", result.script)

    def test_repo2run_open_compiler_captures_ambient_runtime_and_compounds(self) -> None:
        result = compile_repo2run_open_program(
            [
                {
                    "command": "cd /repo && poetry install --with dev",
                    "returncode": 0,
                    "dir": "/repo",
                },
                {
                    "command": "test -d .venv || python -m venv .venv",
                    "returncode": 0,
                    "dir": "/repo",
                },
            ]
        )

        self.assertEqual(result.unsupported_commands, ())
        self.assertIn('grep -E "^3\\.10(\\.|$)"', result.script)
        self.assertIn("poetry install --with dev", result.script)
        self.assertIn(
            'source "$(poetry env info --path)/bin/activate"',
            result.script,
        )
        self.assertIn("test -d .venv || python -m venv .venv", result.script)
        self.assertEqual(
            result.actions[0].source_command,
            "ambient-runtime:python:3.10",
        )
        self.assertEqual(
            result.actions[-1].source_command,
            "native-verifier-context:poetry-run",
        )

    def test_repository_effect_audit_requires_adapter_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.test"],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"], cwd=repo, check=True
            )
            (repo / "module.py").write_text("VALUE = 1\n")
            subprocess.run(["git", "add", "module.py"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            precondition = WorkspacePrecondition(
                "build_output", producer="synthetic-adapter"
            )
            precondition.materialize(repo)
            self.assertTrue(
                inspect_repository(
                    repo,
                    head,
                    required_preconditions=(precondition,),
                ).valid
            )

            (repo / "module.py").write_text("VALUE = 2\n")
            (repo / "build_output").rmdir()
            report = inspect_repository(
                repo,
                head,
                required_preconditions=(precondition,),
            )
            self.assertFalse(report.valid)
            self.assertEqual(
                {item.kind for item in report.violations},
                {"tracked_change", "workspace_precondition_missing"},
            )

    def test_repository_effect_audit_allows_generated_dependency_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.test"],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"], cwd=repo, check=True
            )
            (repo / "package.py").write_text("VALUE = 1\n")
            subprocess.run(["git", "add", "package.py"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            package = repo / "node_modules/package"
            package.mkdir(parents=True)
            (package / "index.js").write_text("module.exports = {}\n")
            (repo / "node_modules/link").symlink_to(package, target_is_directory=True)

            report = inspect_repository(repo, head)

            self.assertTrue(report.valid)
            self.assertEqual(report.allowed_generated_paths, ("node_modules/",))

    def test_verifier_rejects_an_inadmissible_effect_before_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            (worktree / "module.py").write_text("VALUE = 1\n")
            environment = ProvisionedEnvironment(
                EnvironmentReceipt(
                    "container-1",
                    "fixture-provider",
                    "sha256:image",
                    "owner/repo",
                    "a" * 40,
                    "2026-07-21T00:00:00+00:00",
                ),
                DockerEnvironmentHandle(
                    "container-1",
                    worktree,
                    "/data/project",
                ),
            )
            verifier = PythonDeploymentVerifier(
                collect_tests=False,
                effect_auditor=lambda _: _AuditReport(False),
                run_command=lambda command, **kwargs: subprocess.CompletedProcess(
                    command, 0, "", ""
                ),
            )
            result = verifier.verify(
                DeploymentCandidate("candidate-1", "true\n", "No-op"),
                environment,
            )

            self.assertFalse(result.passed)
            self.assertIn("effect boundaries", result.summary)
            self.assertFalse(
                result.details["repository_effect_audit"]["valid"]
            )

    def test_open_program_instrumentation_does_not_split_shell_control_flow(self) -> None:
        commands: list[list[str]] = []

        def run_command(command, **kwargs):
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            (worktree / "module.py").write_text("VALUE = 1\n")
            environment = ProvisionedEnvironment(
                EnvironmentReceipt(
                    "container-1",
                    "fixture-provider",
                    "sha256:image",
                    "owner/repo",
                    "a" * 40,
                    "2026-07-21T00:00:00+00:00",
                ),
                DockerEnvironmentHandle("container-1", worktree, "/data/project"),
            )
            verifier = PythonDeploymentVerifier(
                collect_tests=False,
                effect_auditor=lambda _: _AuditReport(True),
                run_command=run_command,
            )
            candidate = DeploymentCandidate(
                "candidate-1",
                "if true; then\n  printf 'ready\\n'\nfi\n",
                "Use ordinary shell control flow",
                metadata={
                    "candidate_validation": {
                        "policy_id": "open-candidate-program-v1",
                        "details": {},
                    }
                },
            )
            verifier.verify(candidate, environment)

        executed_shell = commands[0][-1]
        self.assertIn("if true; then\n  printf 'ready\\n'\nfi", executed_shell)
        self.assertNotIn("if true; then\nENVSOLVE_ACTION_INDEX", executed_shell)


if __name__ == "__main__":
    unittest.main()
