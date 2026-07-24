from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from envsolve_harness.core.models import Case, RunSpec
from envsolve_harness.runners.codex_cli import (
    CodexCliRunner,
    audit_script_grounding,
    parse_codex_usage,
)
from envsolve.runtime import ExecutableGoalContract
from envsolve.runtime.workspace import WorkspacePrecondition


class CodexCliRunnerTest(unittest.TestCase):
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
            self.assertIn("public-import-goal", goal_aware)
            self.assertIn(contract.sha256, goal_aware)
            self.assertIn(contract.program, goal_aware)
            self.assertIn("official evaluator output is available", goal_aware)


if __name__ == "__main__":
    unittest.main()
