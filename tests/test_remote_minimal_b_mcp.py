from __future__ import annotations

import argparse
from pathlib import Path
import tempfile
import unittest

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.boundary_v5 import (
    BoundaryV5OfficialAlignedExecutableGoalVerifier,
)
from envsolve_harness.codex.remote_container_mcp import (
    SshProcessTreeSafePersistentContainerShell,
)
from envsolve_harness.codex.remote_minimal_b_mcp_boundary_v5 import build_server
from envsolve_harness.core.io import write_json
from envsolve_harness.execution.remote_docker import RemoteDockerCommandAdapter


class RemoteMinimalBMcpTest(unittest.TestCase):
    def test_terminal_and_clean_replay_share_remote_transport(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "workspace"
            source.mkdir()
            goal = root / "goal.json"
            preconditions = root / "preconditions.json"
            write_json(
                goal,
                ExecutableGoalContract(
                    contract_id="goal",
                    description="goal",
                    program="true",
                ).to_dict(),
            )
            write_json(preconditions, [])
            args = argparse.Namespace(
                container_id="construction",
                workdir="/data/project",
                command_trace=root / "commands.jsonl",
                replay_trace=root / "replays.jsonl",
                certification=root / "certification.json",
                programs_root=root / "programs",
                source_repository=source,
                worktrees=root / "worktrees",
                repository="owner/repo",
                revision="a" * 40,
                image="sha256:test",
                goal_contract=goal,
                workspace_preconditions=preconditions,
                command_timeout=30,
                container_create_timeout=10,
                max_output_chars=16000,
                ssh_target="user@executor",
                remote_workspace_root="/srv/envsolve",
                ssh_executable="ssh",
                ssh_identity="/tmp/test-identity",
                ssh_port=2222,
                docker="docker",
                expose_gpus=False,
            )

            server = build_server(args)

            executor = server.terminal.executor
            provider = server.replay_service.provider
            verifier = server.replay_service.verifier
            self.assertIsInstance(
                executor,
                SshProcessTreeSafePersistentContainerShell,
            )
            self.assertIsInstance(provider.run_command, RemoteDockerCommandAdapter)
            self.assertIs(provider.run_command, verifier.run_command)
            self.assertIsInstance(
                verifier,
                BoundaryV5OfficialAlignedExecutableGoalVerifier,
            )
            self.assertEqual(executor.ssh_target, "user@executor")
            self.assertEqual(executor.ssh_identity, "/tmp/test-identity")
            self.assertEqual(executor.ssh_port, 2222)
            self.assertEqual(provider.run_command.transport.target, "user@executor")
            self.assertEqual(
                provider.run_command.transport.ssh_identity,
                "/tmp/test-identity",
            )
            self.assertEqual(provider.run_command.transport.ssh_port, 2222)
            self.assertEqual(
                provider.run_command.transport.remote_root,
                "/srv/envsolve",
            )


if __name__ == "__main__":
    unittest.main()
