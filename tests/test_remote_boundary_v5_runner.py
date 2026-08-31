from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.boundary_v5 import (
    BoundaryV5OfficialAlignedExecutableGoalVerifier,
)
from envsolve_harness.core.io import write_json, write_jsonl
from envsolve_harness.core.models import Case, RunSpec, SolverResult
from envsolve_harness.runners.remote_boundary_v5 import (
    OfficialPrimaryRemoteBoundaryV5CodexCliRunner,
    RemoteBoundaryV5QualifiedCodexCliRunner,
    RemoteBoundaryV5QualifiedMinimalBRunner,
)
from envsolve_harness.storage.artifacts import RunArtifacts


class RemoteBoundaryV5RunnerTest(unittest.TestCase):
    @staticmethod
    def _runner(root: Path, runner_type=RemoteBoundaryV5QualifiedCodexCliRunner):
        return runner_type(
            ssh_target="user@spark",
            remote_workspace_root="/srv/envsolve",
            codex_executable=root / "codex",
            harness_root=root,
            source_cache_root=root / "cache",
            image="envbench:test",
            timeout=120,
            command_timeout=30,
            container_create_timeout=10,
            git_fetch_timeout=20,
            goal_contract=ExecutableGoalContract(
                contract_id="goal",
                description="goal",
                program="true",
            ),
        )

    def test_mcp_keeps_codex_local_and_routes_only_container_tools(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = self._runner(root)

            arguments = runner._mcp_server_args(
                trace_path=root / "trace.jsonl",
                container_id="container",
                case=None,
                image_digest="sha256:test",
            )

            self.assertIn("envsolve_harness.codex.remote_container_mcp", arguments)
            self.assertIn("--ssh-target", arguments)
            self.assertIn("user@spark", arguments)
            self.assertEqual(arguments.count("--docker"), 1)

    def test_container_reuses_spark_acquired_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            workspace.mkdir()
            runner = self._runner(root)
            transport = MagicMock()
            transport.checked_docker.side_effect = ["container", "", ""]
            runner.transport = transport
            runner._remote_source_paths[workspace.resolve()] = (
                "/srv/envsolve/source/exact-checkout"
            )

            container_id = runner._create_container(workspace, "sha256:test")

            self.assertEqual(container_id, "container")
            create = transport.checked_docker.call_args_list[0].args[0]
            self.assertIn(
                "type=bind,src=/srv/envsolve/source/exact-checkout,dst=/data/project",
                create,
            )
            transport.sync_to_remote.assert_called_once_with(
                workspace,
                "/srv/envsolve/source/exact-checkout",
                timeout=20,
            )

    def test_minimal_b_keeps_agent_local_and_routes_online_replay_remotely(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = self._runner(root, RemoteBoundaryV5QualifiedMinimalBRunner)

            arguments = runner._mcp_server_args(
                trace_path=root / "trace.jsonl",
                container_id="container",
                case=Case("case", "owner/repo", "a" * 40),
                image_digest="sha256:test",
            )

            self.assertIn(
                "envsolve_harness.codex.remote_minimal_b_mcp_boundary_v5",
                arguments,
            )
            self.assertIn("--replay-trace", arguments)
            self.assertIn("--ssh-target", arguments)
            self.assertIn("user@spark", arguments)
            self.assertIn("--remote-workspace-root", arguments)
            self.assertIn("/srv/envsolve", arguments)
            self.assertEqual(arguments.count("--docker"), 1)
            self.assertIn("submit_and_replay", runner._mcp_tool_names())

    def test_remote_docker_executable_reaches_terminal_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = RemoteBoundaryV5QualifiedMinimalBRunner(
                ssh_target="user@agenthub",
                remote_workspace_root="/srv/envsolve",
                docker_executable="/usr/local/bin/docker",
                codex_executable=root / "codex",
                harness_root=root,
                source_cache_root=root / "cache",
                image="envbench:test",
                timeout=120,
                command_timeout=30,
                container_create_timeout=10,
                git_fetch_timeout=20,
                goal_contract=ExecutableGoalContract(
                    contract_id="goal",
                    description="goal",
                    program="true",
                ),
            )

            arguments = runner._mcp_server_args(
                trace_path=root / "trace.jsonl",
                container_id="container",
                case=Case("case", "owner/repo", "a" * 40),
                image_digest="sha256:test",
            )

            docker_index = arguments.index("--docker")
            self.assertEqual(arguments[docker_index + 1], "/usr/local/bin/docker")

    def test_remote_minimal_b_accepts_official_aligned_replay_certificate(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = RunArtifacts.create(root / "runs", "run", "case")
            replay_path = artifacts.generation_dir / "minimal-b" / "replays.jsonl"
            write_jsonl(
                replay_path,
                [
                    {
                        "replay_id": "replay-1",
                        "program_sha256": "program-1",
                        "status": "pass",
                        "certified": True,
                        "verification": {
                            "check_profile": (
                                "official-aligned-executable-goal-boundary-v5-v1"
                            )
                        },
                    }
                ],
            )
            runner = self._runner(root, RemoteBoundaryV5QualifiedMinimalBRunner)

            result = runner._certificate_integrity(
                "true",
                artifacts,
                {
                    "minimal_b": {
                        "accepted_certificate": {"replay_id": "replay-1"},
                        "final_program_sha256": "program-1",
                    }
                },
            )

            self.assertIsNotNone(result)
            self.assertTrue(result["valid"])

    def test_official_primary_recovers_admissible_submission_from_advisory_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = RunArtifacts.create(root / "runs", "run", "case")
            output = artifacts.generation_dir / "codex-control" / "final-output.json"
            write_json(
                output,
                {
                    "bootstrap_script": "python -m pip install -e .",
                    "summary": "done",
                },
            )
            initial = SolverResult(
                False,
                "codex-cli-goal-aware-boundary-v5",
                trajectory_path="generation/trajectory.jsonl",
                error="RuntimeError: submitted program integrity failed: advisory",
                metadata={"process_exit_code": 0, "timed_out": False},
            )

            class TestRunner(OfficialPrimaryRemoteBoundaryV5CodexCliRunner):
                def _finish(self, artifacts, result, log):  # type: ignore[no-untyped-def]
                    return result

            runner = self._runner(root, TestRunner)
            with patch.object(
                RemoteBoundaryV5QualifiedCodexCliRunner,
                "run",
                return_value=initial,
            ):
                result = runner.run(
                    Case("case", "owner/repo", "a" * 40),
                    artifacts,
                    RunSpec(
                        "run",
                        "codex-cli-goal-aware-boundary-v5",
                        "gpt-5.5",
                    ),
                )

            self.assertTrue(result.generation_completed)
            self.assertTrue(artifacts.generated_script.is_file())
            self.assertTrue(
                result.metadata["official_primary_submission"][
                    "qualification_is_advisory"
                ]
            )

    def test_official_aligned_verifier_keeps_shell_isolation_without_python_audit(
        self,
    ) -> None:
        from envsolve.runtime.docker import DockerEnvironmentHandle
        from envsolve.solver import DeploymentCandidate

        verifier = BoundaryV5OfficialAlignedExecutableGoalVerifier(
            ExecutableGoalContract("goal", "goal", "true")
        )
        command, _, _ = verifier._command(
            DeploymentCandidate(
                "candidate",
                "python -m pip install demo",
                "exercise an ordinary dependency installation",
            ),
            DockerEnvironmentHandle("container", Path("/tmp/repo"), "/data/project"),
            "nonce",
        )

        self.assertIn("/bin/bash --noprofile --norc -p", command)
        self.assertNotIn("ENVSOLVE_PYTHON_INSTALLATION_BASELINE_V2", command)
        self.assertNotIn("ENVSOLVE_PYTHON_INSTALLATION_POST_V2", command)


if __name__ == "__main__":
    unittest.main()
