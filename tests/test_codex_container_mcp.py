from __future__ import annotations

import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from envsolve_harness.codex.container_mcp import (
    ContainerCommandResult,
    ContainerMcpServer,
    PersistentContainerShell,
)


class FakeExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None]] = []
        self.closed = False

    def execute(
        self, command: str, timeout_seconds: int | None = None
    ) -> ContainerCommandResult:
        self.calls.append((command, timeout_seconds))
        return ContainerCommandResult(command, 7, "observed\n", 0.25)

    def close(self) -> None:
        self.closed = True


class ContainerMcpServerTest(unittest.TestCase):
    def test_serves_initialize_tools_and_audited_command_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace.jsonl"
            executor = FakeExecutor()
            server = ContainerMcpServer(executor, trace)
            requests = [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18"},
                },
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "container_exec",
                        "arguments": {"command": "false", "timeout_seconds": 9},
                    },
                },
            ]
            source = io.StringIO("".join(json.dumps(item) + "\n" for item in requests))
            target = io.StringIO()

            server.serve(source, target)

            responses = [json.loads(line) for line in target.getvalue().splitlines()]
            self.assertEqual([item["id"] for item in responses], [1, 2, 3])
            self.assertEqual(
                responses[1]["result"]["tools"][0]["name"], "container_exec"
            )
            tool_result = responses[2]["result"]
            self.assertFalse(tool_result["isError"])
            self.assertEqual(tool_result["structuredContent"]["exit_code"], 7)
            self.assertEqual(executor.calls, [("false", 9)])
            self.assertTrue(executor.closed)
            record = json.loads(trace.read_text().strip())
            self.assertEqual(record["sequence"], 1)
            self.assertEqual(record["command"], "false")

    def test_rejects_invalid_tool_arguments_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executor = FakeExecutor()
            server = ContainerMcpServer(executor, Path(directory) / "trace.jsonl")

            response = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "container_exec",
                        "arguments": {"command": "pwd", "timeout_seconds": True},
                    },
                }
            )

            self.assertEqual(response["error"]["code"], -32602)
            self.assertEqual(executor.calls, [])


@unittest.skipUnless(
    os.environ.get("ENVSOLVE_CODEX_MCP_DOCKER_TEST") == "1",
    "set ENVSOLVE_CODEX_MCP_DOCKER_TEST=1 to run the real container bridge test",
)
class PersistentContainerShellIntegrationTest(unittest.TestCase):
    def test_shell_state_persists_across_tool_calls(self) -> None:
        image = "ghcr.io/jetbrains-research/envbench-python:latest"
        created = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--entrypoint",
                "/bin/bash",
                image,
                "-lc",
                "while true; do sleep 1000; done",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        container_id = created.stdout.strip()
        shell = PersistentContainerShell(
            container_id,
            "/tmp",
            command_timeout=30,
            max_output_chars=16000,
        )
        try:
            first = shell.execute("mkdir -p state && cd state && export ENVSOLVE_STATE=ready")
            second = shell.execute('printf "%s:%s\\n" "$PWD" "$ENVSOLVE_STATE"')
            failure = shell.execute("false")

            self.assertEqual(first.exit_code, 0, first)
            self.assertEqual(second.exit_code, 0, second)
            self.assertEqual(second.output.strip(), "/tmp/state:ready")
            self.assertEqual(failure.exit_code, 1)
            self.assertIsNone(failure.infrastructure_error)
        finally:
            shell.close()
            subprocess.run(
                ["docker", "rm", "-f", container_id],
                capture_output=True,
                text=True,
                check=False,
            )


if __name__ == "__main__":
    unittest.main()
