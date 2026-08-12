from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from envsolve.runtime import ExecutableGoalContract
from envsolve_harness.codex.minimal_b_mcp import CERTIFICATION_SCHEMA, script_sha256
from envsolve_harness.core.io import read_json, write_json, write_jsonl
from envsolve_harness.core.models import (
    BenchmarkConfig,
    Case,
    HarnessConfig,
    RunSpec,
)
from envsolve_harness.core.protocol import ExperimentProtocol, SuccessCriteria
from envsolve_harness.runners.envsolve_pro_minimal_b import (
    METHOD,
    EnvSolveProMinimalBRunner,
)
from envsolve_harness.runners.registry import RunnerOptions
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.utils.provenance import sha256_file
from experiments.run_minimal_b_case import RUNNER_ID, _factory


class EnvSolveProMinimalBRunnerTest(unittest.TestCase):
    def _runner(self, root: Path) -> EnvSolveProMinimalBRunner:
        return EnvSolveProMinimalBRunner(
            codex_executable=root / "codex",
            harness_root=root,
            image="sha256:image",
            timeout=120,
            command_timeout=30,
            container_create_timeout=10,
            git_fetch_timeout=20,
            reasoning_effort="high",
            goal_contract=ExecutableGoalContract(
                "public-goal",
                "Require success",
                "printf '{}\\n' > \"$ENVSOLVE_GOAL_REPORT\"",
            ),
        )

    def test_prompt_and_command_add_only_online_clean_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = self._runner(root)
            case = Case("case", "owner/repo", "abc123")
            trace = root / "generation" / "container-commands.jsonl"
            prompt = runner._prompt(case, runner.goal_contract)
            command = runner._codex_command(
                run_spec=RunSpec("run", METHOD, "gpt-5.5"),
                control_dir=root / "control",
                schema_path=root / "schema.json",
                output_path=root / "output.json",
                trace_path=trace,
                container_id="construction-container",
                case=case,
                image_digest="sha256:image",
            )
            rendered = "\n".join(command)

            self.assertIn("MUST call `submit_and_replay`", prompt)
            self.assertIn("this one conversation", prompt)
            self.assertIn("envsolve_harness.codex.minimal_b_mcp", rendered)
            self.assertIn("submit_and_replay", rendered)
            self.assertIn(
                "mcp_servers.envsolve_container.tools.submit_and_replay.approval_mode=\"approve\"",
                rendered,
            )
            self.assertNotIn("constraint ledger", prompt.lower())
            self.assertNotIn("checkpoint", prompt.lower())

    def test_final_submission_must_match_a_passing_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = RunArtifacts.create(root, "run", "case")
            runner = self._runner(root)
            script = "python -m pip install -e ."
            digest = script_sha256(script)
            image_digest = "sha256:image"
            revision = "abc123"
            minimal_b = artifacts.generation_dir / "minimal-b"
            write_json(
                minimal_b / "certification.json",
                {
                    "schema": CERTIFICATION_SCHEMA,
                    "repository": "owner/repo",
                    "revision": revision,
                    "image_digest": image_digest,
                    "goal_contract_sha256": runner.goal_contract.sha256,
                    "replay_count": 1,
                    "certified_programs": [
                        {
                            "replay_id": "minimal-b-replay-0001",
                            "program_sha256": digest,
                            "environment_receipt": {
                                "revision": revision,
                                "image_digest": image_digest,
                            },
                        }
                    ],
                },
            )
            write_jsonl(
                minimal_b / "replays.jsonl",
                [
                    {
                        "schema": "envsolve-pro-minimal-b-clean-replay-v1",
                        "replay_id": "minimal-b-replay-0001",
                        "status": "pass",
                        "certified": True,
                        "program_sha256": digest,
                    }
                ],
            )
            metadata = {
                "minimal_b": {},
                "checked_out_revision": revision,
                "image_digest": image_digest,
            }

            runner._validate_additional_submission(script, artifacts, metadata)

            self.assertEqual(metadata["minimal_b"]["final_program_sha256"], digest)
            with self.assertRaisesRegex(RuntimeError, "did not pass"):
                runner._validate_additional_submission(
                    "python -m pip install requests",
                    artifacts,
                    {
                        "minimal_b": {},
                        "checked_out_revision": revision,
                        "image_digest": image_digest,
                    },
                )

    def test_isolated_factory_builds_runner_without_changing_builtin_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = HarnessConfig(
                workspace_root=root,
                runs_root=root / "runs",
                benchmarks={
                    "synthetic": BenchmarkConfig(
                        "synthetic",
                        "synthetic",
                        root,
                        {"image": "sha256:image"},
                    )
                },
            )
            protocol = ExperimentProtocol(
                "test",
                "1",
                "synthetic",
                "python",
                (SuccessCriteria("exit_code", "eq", 0),),
                (),
            )
            contract = ExecutableGoalContract(
                "public-goal",
                "Require success",
                "printf '{}\\n' > \"$ENVSOLVE_GOAL_REPORT\"",
            )
            with patch(
                "experiments.run_minimal_b_case.goal_contract_for",
                return_value=contract,
            ), patch(
                "experiments.run_minimal_b_case.workspace_preconditions_for",
                return_value=(),
            ):
                runner = _factory(
                    config,
                    protocol,
                    RunSpec("run", METHOD, "gpt-5.5"),
                    RunnerOptions(),
                )

        self.assertEqual(RUNNER_ID, "envsolve-pro-minimal-b")
        self.assertIsInstance(runner, EnvSolveProMinimalBRunner)

    def test_implementation_freeze_hashes_match(self) -> None:
        root = Path(__file__).resolve().parents[1]
        freeze = read_json(
            root
            / "experiments"
            / "protocols"
            / "envsolve_pro_minimal_b_v1_0_2_implementation_freeze.json"
        )

        design = freeze["design_freeze"]
        self.assertEqual(
            sha256_file(root / design["path"]),
            design["sha256"],
        )
        for relative_path, expected in freeze["source_sha256"].items():
            self.assertEqual(
                sha256_file(root / relative_path),
                expected,
                relative_path,
            )


if __name__ == "__main__":
    unittest.main()
