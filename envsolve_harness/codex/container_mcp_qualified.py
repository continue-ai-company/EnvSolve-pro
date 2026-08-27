#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import os
import re
import selectors
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

from envsolve_harness.codex.container_mcp import (
    ContainerCommandResult,
    ContainerMcpServer,
    PersistentContainerShell,
    _bounded_output,
)


class ProcessTreeSafePersistentContainerShell(PersistentContainerShell):
    """Persistent shell that removes container descendants after a timeout."""

    def __init__(
        self,
        container_id: str,
        workdir: str,
        command_timeout: int,
        max_output_chars: int,
        docker_executable: str = "docker",
    ) -> None:
        super().__init__(
            container_id,
            workdir,
            command_timeout,
            max_output_chars,
            docker_executable,
        )
        self._container_shell_pid: int | None = None

    def _start(self) -> subprocess.Popen[bytes]:
        running = self._process is not None and self._process.poll() is None
        process = super()._start()
        if not running:
            self._container_shell_pid = None
        return process

    def _stop(self) -> None:
        super()._stop()
        self._container_shell_pid = None

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
                [
                    self.docker_executable,
                    "exec",
                    "--user",
                    "0:0",
                    self.container_id,
                    "/bin/bash",
                    "-c",
                    cleanup_script,
                    "--",
                    str(shell_pid),
                ],
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
                return "container process-tree cleanup timed out"
        except OSError as exc:
            return f"container process-tree cleanup failed: {type(exc).__name__}: {exc}"
        if process.returncode != 0:
            return (
                "container process-tree cleanup failed with "
                f"exit {process.returncode}: {stderr.strip()}"
            )
        return None

    def execute(
        self,
        command: str,
        timeout_seconds: int | None = None,
    ) -> ContainerCommandResult:
        command = command.strip()
        if not command:
            return ContainerCommandResult(
                command=command,
                exit_code=None,
                output="",
                duration_seconds=0.0,
                infrastructure_error="command cannot be empty",
            )
        timeout = min(timeout_seconds or self.command_timeout, self.command_timeout)
        if timeout <= 0:
            return ContainerCommandResult(
                command=command,
                exit_code=None,
                output="",
                duration_seconds=0.0,
                infrastructure_error="timeout_seconds must be positive",
            )
        started = time.monotonic()
        try:
            process = self._start()
        except OSError as exc:
            return ContainerCommandResult(
                command=command,
                exit_code=None,
                output="",
                duration_seconds=time.monotonic() - started,
                infrastructure_error=f"{type(exc).__name__}: {exc}",
            )
        if process.stdin is None or process.stdout is None:
            self._stop()
            return ContainerCommandResult(
                command=command,
                exit_code=None,
                output="",
                duration_seconds=time.monotonic() - started,
                infrastructure_error="persistent container shell has no stdio",
            )

        nonce = uuid.uuid4().hex
        start_marker = f"__ENVSOLVE_CODEX_MCP_START_{nonce}__=".encode()
        done_marker = f"__ENVSOLVE_CODEX_MCP_DONE_{nonce}__=".encode()
        encoded = base64.b64encode(command.encode("utf-8")).decode("ascii")
        wrapper = (
            f"printf '{start_marker.decode()}%s\\n' \"$$\"\n"
            "set -o pipefail\n"
            f"eval \"$(printf '%s' '{encoded}' | base64 --decode)\"\n"
            "__envsolve_codex_rc=$?\n"
            f"printf '\\n{done_marker.decode()}%s\\n' \"$__envsolve_codex_rc\"\n"
        ).encode()
        try:
            process.stdin.write(wrapper)
            process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self._stop()
            return ContainerCommandResult(
                command=command,
                exit_code=None,
                output="",
                duration_seconds=time.monotonic() - started,
                infrastructure_error=(
                    f"container shell write failed: {type(exc).__name__}: {exc}"
                ),
            )

        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = started + timeout
        payload = self._buffer
        self._buffer = b""
        start_pattern = re.compile(re.escape(start_marker) + rb"(\d+)\r?\n")
        done_pattern = re.compile(re.escape(done_marker) + rb"(-?\d+)\r?\n")
        try:
            while True:
                start_match = start_pattern.search(payload)
                if start_match is not None:
                    self._container_shell_pid = int(start_match.group(1))
                done_match = done_pattern.search(payload)
                if done_match is not None:
                    output_start = start_match.end() if start_match is not None else 0
                    output_bytes = payload[output_start : done_match.start()]
                    self._buffer = payload[done_match.end() :]
                    output = output_bytes.decode("utf-8", errors="replace").lstrip(
                        "\r\n"
                    )
                    bounded, truncated = _bounded_output(output, self.max_output_chars)
                    return ContainerCommandResult(
                        command=command,
                        exit_code=int(done_match.group(1)),
                        output=bounded,
                        duration_seconds=time.monotonic() - started,
                        output_truncated=truncated,
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    output_start = start_match.end() if start_match is not None else 0
                    bounded, truncated = _bounded_output(
                        payload[output_start:].decode("utf-8", errors="replace"),
                        self.max_output_chars,
                    )
                    cleanup_error = self._terminate_container_process_tree()
                    self._stop()
                    return ContainerCommandResult(
                        command=command,
                        exit_code=None,
                        output=bounded,
                        duration_seconds=time.monotonic() - started,
                        timed_out=True,
                        output_truncated=truncated,
                        infrastructure_error=cleanup_error,
                    )
                events = selector.select(timeout=remaining)
                if not events:
                    continue
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    return_code = process.poll()
                    bounded, truncated = _bounded_output(
                        payload.decode("utf-8", errors="replace"),
                        self.max_output_chars,
                    )
                    self._stop()
                    return ContainerCommandResult(
                        command=command,
                        exit_code=None,
                        output=bounded,
                        duration_seconds=time.monotonic() - started,
                        output_truncated=truncated,
                        infrastructure_error=(
                            f"persistent container shell exited with {return_code}"
                        ),
                    )
                payload += chunk
        finally:
            selector.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process-tree-safe container MCP terminal for Codex."
    )
    parser.add_argument("--container-id", required=True)
    parser.add_argument("--workdir", default="/data/project")
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--command-timeout", type=int, required=True)
    parser.add_argument("--max-output-chars", type=int, default=16000)
    parser.add_argument("--docker", default="docker")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    executor = ProcessTreeSafePersistentContainerShell(
        args.container_id,
        args.workdir,
        args.command_timeout,
        args.max_output_chars,
        args.docker,
    )
    ContainerMcpServer(executor, args.trace).serve(sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
