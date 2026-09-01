from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from envsolve_harness.core.models import Case, RunSpec
from envsolve_harness.core.io import write_json
from envsolve_harness.execution.process import checked_output
from envsolve_harness.runners.codex_cli import (
    CodexCliRunner,
    audit_script_grounding,
    parse_codex_usage,
    validate_codex_bootstrap,
)
from envsolve_harness.scripts.open_program import OpenCandidateProgramValidator
from envsolve.runtime import ExecutableGoalContract
from envsolve.solver import CandidateValidation
from envsolve.runtime.workspace import WorkspacePrecondition
from envsolve_harness.storage.artifacts import RunArtifacts


class CodexCliRunnerTest(unittest.TestCase):
    def test_checked_timeout_terminates_the_complete_process_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child_pid_path = Path(directory) / "child.pid"
            program = (
                "import pathlib, subprocess, sys, time; "
                "child=subprocess.Popen([sys.executable, '-c', "
                "'import time; time.sleep(60)']); "
                "pathlib.Path(sys.argv[1]).write_text(str(child.pid)); "
                "time.sleep(60)"
            )

            with self.assertRaises(subprocess.TimeoutExpired):
                checked_output(
                    [sys.executable, "-c", program, str(child_pid_path)],
                    timeout=1,
                )

            child_pid = int(child_pid_path.read_text())
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.05)
            else:
                self.fail(f"timed-out child process {child_pid} survived")

    def test_bootstrap_uses_shared_open_program_integrity_policy(self) -> None:
        accepted = validate_codex_bootstrap("python -m pip install -e .\n")
        rejected = validate_codex_bootstrap(
            "cp build/fake.so package/fake.so\n"
        )

        self.assertTrue(accepted.accepted)
        self.assertFalse(rejected.accepted)
        self.assertIn("importable artifact", rejected.reason)

    def test_run_dispatches_final_validation_through_runner_hook(self) -> None:
        class HookedRunner(CodexCliRunner):
            observed_scripts: list[str]

            def _acquire_repository(self, case, destination):
                del case
                destination.mkdir()
                return []

            def _image_digest(self):
                return "sha256:fixture"

            def _create_container(self, workspace, image_digest):
                del workspace, image_digest
                return "fixture-container"

            def _codex_command(self, **kwargs):
                del kwargs
                return ["fixture-codex"]

            def _has_required_tool_activity(self, successful_command_count, metadata):
                del successful_command_count, metadata
                return True

            def _validate_bootstrap(self, script):
                self.observed_scripts.append(script)
                return CandidateValidation(
                    accepted=True,
                    policy_id="fixture-versioned-policy",
                    normalized_script=script,
                )

        class FakeProcess:
            returncode = 0

            def __init__(self, output_path: Path, script: str) -> None:
                self.output_path = output_path
                self.script = script

            def communicate(self, input=None, timeout=None):
                del input, timeout
                write_json(
                    self.output_path,
                    {"bootstrap_script": self.script, "summary": "fixture"},
                )
                return ('{"type":"turn.completed","usage":{}}\n', "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            codex = root / "codex"
            codex.touch()
            artifacts = RunArtifacts.create(root / "runs", "run", "case")
            write_json(artifacts.manifest, {"solver": None})
            script = "mkdir -p src/pkg\nprintf 'VALUE = 1\\n' > src/pkg/generated.py"
            runner = HookedRunner(
                codex_executable=codex,
                harness_root=root,
                image="envbench:test",
                timeout=120,
                command_timeout=30,
                container_create_timeout=10,
                git_fetch_timeout=20,
            )
            runner.observed_scripts = []
            integrity = SimpleNamespace(
                valid=True,
                checked_out_revision="a" * 40,
                to_dict=lambda: {
                    "valid": True,
                    "checked_out_revision": "a" * 40,
                    "violations": [],
                },
            )
            output_path = artifacts.generation_dir / "codex-control" / "final-output.json"

            with (
                patch(
                    "envsolve_harness.runners.codex_cli.subprocess.Popen",
                    return_value=FakeProcess(output_path, script),
                ),
                patch(
                    "envsolve_harness.runners.codex_cli.subprocess.run",
                    return_value=SimpleNamespace(
                        stdout="codex fixture", stderr="", returncode=0
                    ),
                ),
                patch(
                    "envsolve_harness.runners.codex_cli.inspect_repository",
                    return_value=integrity,
                ),
                patch("envsolve_harness.runners.codex_cli.cleanup_case_containers"),
            ):
                result = runner.run(
                    Case("case", "org/repo", "a" * 40),
                    artifacts,
                    RunSpec("run", "fixture", "gpt-fixture"),
                )

            self.assertTrue(result.generation_completed, result.error)
            self.assertEqual(runner.observed_scripts, [script])
            self.assertEqual(
                result.metadata["candidate_validation"]["policy_id"],
                "fixture-versioned-policy",
            )

    def test_usage_aggregation_and_non_gating_script_grounding(self) -> None:
        usage = parse_codex_usage(
            [
                {
                    "type": "turn.completed",
                    "usage": {
                        "input_tokens": 10,
                        "cached_input_tokens": 4,
                        "output_tokens": 2,
                    },
                },
                {
                    "type": "turn.completed",
                    "usage": {"input_tokens": 3, "output_tokens": 1},
                },
            ]
        )
        grounding = audit_script_grounding(
            "set -euo pipefail\npip install -e .\nexport DEMO=1\n",
            [
                {"command": "pip install -e .", "exit_code": 0},
                {"command": "export DEMO=2", "exit_code": 0},
                {"command": "pytest", "exit_code": 1},
            ],
        )

        self.assertEqual(usage["input_tokens"], 13)
        self.assertEqual(usage["output_tokens"], 3)
        self.assertEqual(grounding["grounded_line_count"], 1)
        self.assertEqual(grounding["ungrounded_lines"], ["export DEMO=1"])
        self.assertFalse(grounding["is_gate"])

    def test_codex_command_disables_host_shell_and_external_tools(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = CodexCliRunner(
                codex_executable=root / "codex",
                harness_root=root,
                image="envbench:test",
                timeout=120,
                command_timeout=30,
                container_create_timeout=10,
                git_fetch_timeout=20,
                reasoning_effort="high",
            )
            command = runner._codex_command(
                run_spec=RunSpec("run", "codex", "gpt-5.5"),
                control_dir=root,
                schema_path=root / "schema.json",
                output_path=root / "output.json",
                trace_path=root / "trace.jsonl",
                container_id="container-id",
            )
            rendered = "\n".join(command)

            self.assertIn("features.shell_tool=false", rendered)
            self.assertIn("features.apps=false", rendered)
            self.assertIn("web_search=\"disabled\"", rendered)
            self.assertIn("mcp_servers.envsolve_container.required=true", rendered)
            self.assertIn(
                "mcp_servers.envsolve_container.default_tools_approval_mode=\"approve\"",
                rendered,
            )
            self.assertIn(
                "mcp_servers.envsolve_container.tools.envbench_shell.approval_mode=\"approve\"",
                rendered,
            )
            self.assertIn("gpt-5.5", command)
            self.assertIn("--ephemeral", command)
            self.assertIn("--ignore-user-config", command)
            self.assertEqual(command[-1], "-")

    def test_materializes_adapter_workspace_preconditions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = CodexCliRunner(
                codex_executable=root / "codex",
                harness_root=root,
                image="envbench:test",
                timeout=120,
                command_timeout=30,
                container_create_timeout=10,
                git_fetch_timeout=20,
                workspace_preconditions=(
                    WorkspacePrecondition(
                        "build_output",
                        producer="synthetic-adapter",
                    ),
                ),
            )

            runner._materialize_workspace_preconditions(root)

            self.assertTrue((root / "build_output").is_dir())

    def test_goal_aware_prompt_adds_only_the_public_goal_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = ExecutableGoalContract(
                contract_id="public-import-goal",
                description="Require zero missing imports",
                program="python -m pyright . --outputjson",
            )
            runner = CodexCliRunner(
                codex_executable=root / "codex",
                harness_root=root,
                image="envbench:test",
                timeout=120,
                command_timeout=30,
                container_create_timeout=10,
                git_fetch_timeout=20,
                goal_contract=contract,
            )
            case = Case("case", "owner/repo", "abc")

            native = runner._prompt(case)
            goal_aware = runner._prompt(case, contract)

            self.assertNotIn("public-import-goal", native)
            self.assertIn("<candidate_contract>", native)
            self.assertIn(
                OpenCandidateProgramValidator.prompt_contract,
                native,
            )
            self.assertIn("public-import-goal", goal_aware)
            self.assertIn(contract.sha256, goal_aware)
            self.assertIn(contract.program, goal_aware)
            self.assertIn("official evaluator output is available", goal_aware)


if __name__ == "__main__":
    unittest.main()
