#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys

from envsolve_harness.codex.container_mcp import ContainerMcpServer
from envsolve_harness.codex.container_mcp_qualified import (
    ProcessTreeSafePersistentContainerShell,
)


class SshProcessTreeSafePersistentContainerShell(
    ProcessTreeSafePersistentContainerShell
):
    """Keep the qualified persistent shell inside a remote Docker daemon."""

    def __init__(
        self,
        container_id: str,
        workdir: str,
        command_timeout: int,
        max_output_chars: int,
        ssh_target: str,
        ssh_executable: str = "ssh",
        docker_executable: str = "docker",
    ) -> None:
        super().__init__(
            container_id,
            workdir,
            command_timeout,
            max_output_chars,
            docker_executable,
        )
        self.ssh_target = ssh_target
        self.ssh_executable = ssh_executable

    def _ssh_docker_command(self, arguments: list[str]) -> list[str]:
        remote = shlex.join([self.docker_executable, *arguments])
        return [self.ssh_executable, "-T", self.ssh_target, remote]

    def _start(self) -> subprocess.Popen[bytes]:
        if self._process is not None and self._process.poll() is None:
            return self._process
        self._buffer = b""
        self._container_shell_pid = None
        self._process = subprocess.Popen(
            self._ssh_docker_command(
                [
                    "exec",
                    "-i",
                    "--workdir",
                    self.workdir,
                    self.container_id,
                    "/bin/bash",
                    "--noprofile",
                    "--norc",
                ]
            ),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        return self._process

    def _terminate_container_process_tree(self) -> str | None:
        shell_pid = self._container_shell_pid
        if shell_pid is None:
            return "container shell PID was not observed before timeout"
        cleanup_script = r"""
collect_descendants() {
    parent="$1"
    for child in $(ps -eo pid=,ppid= | awk -v parent="$parent" '$2 == parent {print $1}'); do
        collect_descendants "$child"
    done
    printf '%s ' "$parent"
}
targets="$(collect_descendants "$1")"
if [ -n "$targets" ]; then
    kill -TERM $targets 2>/dev/null || true
    sleep 1
    kill -KILL $targets 2>/dev/null || true
fi
""".strip()
        try:
            process = subprocess.Popen(
                self._ssh_docker_command(
                    [
                        "exec",
                        "--user",
                        "0:0",
                        self.container_id,
                        "/bin/bash",
                        "-c",
                        cleanup_script,
                        "--",
                        str(shell_pid),
                    ]
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                _, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.communicate()
                return "remote container process-tree cleanup timed out"
        except OSError as exc:
            return f"remote process-tree cleanup failed: {type(exc).__name__}: {exc}"
        if process.returncode != 0:
            return (
                "remote container process-tree cleanup failed with "
                f"exit {process.returncode}: {stderr.strip()}"
            )
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SSH-backed container MCP terminal.")
    parser.add_argument("--container-id", required=True)
    parser.add_argument("--workdir", default="/data/project")
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--command-timeout", type=int, required=True)
    parser.add_argument("--max-output-chars", type=int, default=16000)
    parser.add_argument("--ssh-target", required=True)
    parser.add_argument("--ssh-executable", default="ssh")
    parser.add_argument("--docker", default="docker")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    executor = SshProcessTreeSafePersistentContainerShell(
        args.container_id,
        args.workdir,
        args.command_timeout,
        args.max_output_chars,
        args.ssh_target,
        args.ssh_executable,
        args.docker,
    )
    ContainerMcpServer(executor, args.trace).serve(sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
