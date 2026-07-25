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
        prompt = " ".join(validator.prompt_contract.split())
        self.assertIn("inserted inline into the controlling Bash process", prompt)
        self.assertIn("use `$PWD`", validator.prompt_contract)

    def test_open_validator_rejects_direct_import_artifact_injection(self) -> None:
        validator = OpenCandidateProgramValidator()
        heredoc = validator.validate(
            DeploymentCandidate(
                "candidate-heredoc",
                "cat > \"$TMPDIR/fake_package.py\" <<'PY'\npass\nPY\n",
                "Inject a module",
            )
        )
        touched = validator.validate(
            DeploymentCandidate(
                "candidate-touch",
                "touch \"$TMPDIR/fake_package/__init__.py\"\n",
                "Inject a package",
            )
        )
        piped = validator.validate(
            DeploymentCandidate(
                "candidate-tee",
                "printf 'pass\\n' | tee \"$TMPDIR/fake_package.py\"\n",
                "Inject through a pipeline",
            )
        )
        build_driver = validator.validate(
            DeploymentCandidate(
                "candidate-build",
                "cat > \"$TMPDIR/setup.py\" <<'PY'\n"
                "from setuptools import setup\n"
                "setup()\n"
                "PY\n"
                "python -m pip install \"$TMPDIR\"\n",
                "Use a temporary build driver",
            )
        )
        generated_in_build_hook = validator.validate(
            DeploymentCandidate(
                "candidate-generated-build-hook",
                "cat > \"$TMPDIR/setup.py\" <<'PY'\n"
                "from setuptools import setup\n"
                "import os\n"
                "\n"
                "def generate_package():\n"
                "    with open(os.path.join('fake_package', '__init__.py'), 'w') as stream:\n"
                "        stream.write('')\n"
                "\n"
                "generate_package()\n"
                "setup(name='fake-package')\n"
                "PY\n"
                "python -m pip install \"$TMPDIR\"\n",
                "Hide module injection in a temporary build hook",
            )
        )
        generated_by_python_c = validator.validate(
            DeploymentCandidate(
                "candidate-python-c",
                "python -c 'open(\"fake_package.py\", \"w\").write(\"pass\")'\n",
                "Inject through embedded Python",
            )
        )
        real_path = validator.validate(
            DeploymentCandidate(
                "candidate-path",
                "export PYTHONPATH=\"$PWD/src:${PYTHONPATH:-}\"\n",
                "Expose real repository source",
            )
        )

        self.assertFalse(heredoc.accepted)
        self.assertEqual(
            heredoc.details["target"],
            "$TMPDIR/fake_package.py",
        )
        self.assertFalse(touched.accepted)
        self.assertFalse(piped.accepted)
        self.assertTrue(build_driver.accepted)
        self.assertFalse(generated_in_build_hook.accepted)
        self.assertEqual(
            generated_in_build_hook.details["target"],
            "__init__.py",
        )
        self.assertFalse(generated_by_python_c.accepted)
        self.assertTrue(real_path.accepted)

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

    def test_repo2run_open_compiler_relocates_only_repo_path_tokens(self) -> None:
        result = compile_repo2run_open_program(
            [
                {
                    "command": "pip install -e /repo -q",
                    "returncode": 0,
                    "dir": "/repo",
                },
                {
                    "command": (
                        'cp "/repo/package/data.json" /tmp/data.json && '
                        "echo https://example.test/repo /repository"
                    ),
                    "returncode": 0,
                    "dir": "/repo",
                },
            ]
        )

        self.assertIn("pip install -e ${PROJECT_ROOT} -q", result.script)
        self.assertIn('"${PROJECT_ROOT}/package/data.json"', result.script)
        self.assertIn("https://example.test/repo", result.script)
        self.assertIn("/repository", result.script)

    def test_repo2run_open_compiler_translates_private_download_helper(self) -> None:
        result = compile_repo2run_open_program(
            [
                {
                    "command": (
                        "python /home/tools/pip_download.py "
                        "-p pytest -v '==8.1.1'"
                    ),
                    "returncode": 0,
                    "dir": "/",
                },
                {
                    "command": (
                        "python /home/tools/pip_download.py "
                        "-p ansible-core==2.17.14"
                    ),
                    "returncode": 0,
                    "dir": "/",
                }
            ]
        )

        self.assertEqual(result.unsupported_commands, ())
        self.assertIn("python -m pip install pytest==8.1.1", result.script)
        self.assertIn(
            "python -m pip install ansible-core==2.17.14",
            result.script,
        )
        self.assertNotIn("/home/tools", result.script)
        self.assertEqual(result.actions[-1].kind, "python_package_install")

    def test_repo2run_open_compiler_rejects_malformed_download_helper(self) -> None:
        command = "python /home/tools/pip_download.py -p 'bad;name'"
        result = compile_repo2run_open_program(
            [{"command": command, "returncode": 0, "dir": "/"}]
        )

        self.assertEqual(result.unsupported_commands, (command,))
        self.assertNotIn("bad;name", result.script)

    def test_repo2run_open_compiler_drops_private_verifier_tools(self) -> None:
        commands = (
            "cat /home/tools/runtest.py",
            (
                "AWS_DEFAULT_REGION=us-east-1 "
                "python /home/tools/runtest.py"
            ),
            "which runtest || ls /home/tools/poetryruntest.py",
        )
        result = compile_repo2run_open_program(
            [
                {"command": command, "returncode": 0, "dir": "/repo"}
                for command in commands
            ]
        )

        self.assertEqual(result.dropped_commands, commands)
        self.assertNotIn("/home/tools", result.script)

    def test_repo2run_open_compiler_rejects_unknown_private_tool(self) -> None:
        command = "python /home/tools/unknown_helper.py"
        result = compile_repo2run_open_program(
            [{"command": command, "returncode": 0, "dir": "/repo"}]
        )

        self.assertEqual(
            result.unsupported_commands,
            (f"private-tool-path: {command}",),
        )
        self.assertNotIn("/home/tools", result.script)

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
