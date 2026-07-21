#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import time
from typing import Any, Protocol, TextIO
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bounded_output(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    half = max(1, limit // 2)
    omitted = len(value) - (2 * half)
    return (
        value[:half]
        + f"\n... {omitted} characters omitted by container bridge ...\n"
        + value[-half:],
        True,
    )


@dataclass(frozen=True)
class ContainerCommandResult:
    command: str
    exit_code: int | None
    output: str
    duration_seconds: float
    timed_out: bool = False
    output_truncated: bool = False
    infrastructure_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CommandExecutor(Protocol):
    def execute(self, command: str, timeout_seconds: int | None = None) -> ContainerCommandResult: ...

    def close(self) -> None: ...


class PersistentContainerShell:
    """One persistent, non-TTY Bash session inside a single Docker container."""

    def __init__(
        self,
        container_id: str,
        workdir: str,
        command_timeout: int,
        max_output_chars: int,
        docker_executable: str = "docker",
    ) -> None:
        if command_timeout <= 0 or max_output_chars <= 0:
            raise ValueError("Container bridge limits must be positive")
        self.container_id = container_id
        self.workdir = workdir
        self.command_timeout = command_timeout
        self.max_output_chars = max_output_chars
        self.docker_executable = docker_executable
        self._process: subprocess.Popen[bytes] | None = None
        self._buffer = b""

    def _start(self) -> subprocess.Popen[bytes]:
        if self._process is not None and self._process.poll() is None:
            return self._process
        self._buffer = b""
        self._process = subprocess.Popen(
            [
                self.docker_executable,
                "exec",
                "-i",
                "--workdir",
                self.workdir,
                self.container_id,
                "/bin/bash",
                "--noprofile",
                "--norc",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        return self._process

    def _stop(self) -> None:
        process = self._process
        self._process = None
        self._buffer = b""
        if process is None:
            return
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=2)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()

    def close(self) -> None:
        self._stop()

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
        marker = f"__ENVSOLVE_CODEX_MCP_DONE_{nonce}__=".encode()
        encoded = base64.b64encode(command.encode("utf-8")).decode("ascii")
        wrapper = (
            f"eval \"$(printf '%s' '{encoded}' | base64 --decode)\"\n"
            "__envsolve_codex_rc=$?\n"
            f"printf '\\n{marker.decode()}%s\\n' \"$__envsolve_codex_rc\"\n"
        ).encode("utf-8")
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
                infrastructure_error=f"container shell write failed: {type(exc).__name__}: {exc}",
            )

        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = started + timeout
        payload = self._buffer
        self._buffer = b""
        marker_pattern = re.compile(re.escape(marker) + rb"(-?\d+)\r?\n")
        try:
            while True:
                match = marker_pattern.search(payload)
                if match is not None:
                    output_bytes = payload[: match.start()]
                    self._buffer = payload[match.end() :]
                    output = output_bytes.decode("utf-8", errors="replace").lstrip("\r\n")
                    bounded, truncated = _bounded_output(output, self.max_output_chars)
                    return ContainerCommandResult(
                        command=command,
                        exit_code=int(match.group(1)),
                        output=bounded,
                        duration_seconds=time.monotonic() - started,
                        output_truncated=truncated,
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
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
                        timed_out=True,
                        output_truncated=truncated,
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


class ContainerMcpServer:
    protocol_version = "2025-06-18"
    tool_name = "envbench_shell"

    def __init__(self, executor: CommandExecutor, trace_path: Path) -> None:
        self.executor = executor
        self.trace_path = trace_path
        self.sequence = 0

    def _trace(self, result: ContainerCommandResult) -> None:
        self.sequence += 1
        record = {
            "schema": "envsolve-codex-container-command-v1",
            "sequence": self.sequence,
            "recorded_at": _now(),
            **result.to_dict(),
        }
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        request_id = request.get("id")
        method = request.get("method")
        if method == "initialize":
            requested = request.get("params", {}).get("protocolVersion")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": (
                        requested if isinstance(requested, str) else self.protocol_version
                    ),
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {
                        "name": "envsolve-container-terminal",
                        "version": "1.0.0",
                    },
                    "instructions": (
                        "Use envbench_shell for every repository inspection, environment "
                        "change, and verification. The shell and container persist between "
                        "calls, and every call starts from the shell's current directory."
                    ),
                },
            }
        if method in {"notifications/initialized", "notifications/cancelled"}:
            return None
        if method == "ping":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": self.tool_name,
                            "description": (
                                "Execute a Bash command in the persistent EnvBench Docker "
                                "container. Filesystem, installed packages, working directory, "
                                "and exported shell variables persist between calls."
                            ),
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "command": {
                                        "type": "string",
                                        "description": "Bash command to execute.",
                                    },
                                    "timeout_seconds": {
                                        "type": "integer",
                                        "minimum": 1,
                                        "description": (
                                            "Optional command timeout, capped by the harness."
                                        ),
                                    },
                                },
                                "required": ["command"],
                                "additionalProperties": False,
                            },
                            "annotations": {
                                "readOnlyHint": False,
                                "destructiveHint": False,
                                "idempotentHint": False,
                                "openWorldHint": True,
                            },
                        }
                    ]
                },
            }
        if method != "tools/call":
            if request_id is None:
                return None
            return self._error(request_id, -32601, f"unsupported method: {method}")

        params = request.get("params")
        if not isinstance(params, dict) or params.get("name") != self.tool_name:
            return self._error(request_id, -32602, "unknown tool")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict) or not isinstance(arguments.get("command"), str):
            return self._error(request_id, -32602, "command must be a string")
        timeout = arguments.get("timeout_seconds")
        if timeout is not None and (not isinstance(timeout, int) or isinstance(timeout, bool)):
            return self._error(request_id, -32602, "timeout_seconds must be an integer")
        result = self.executor.execute(arguments["command"], timeout)
        self._trace(result)
        payload = result.to_dict()
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(payload, ensure_ascii=True, sort_keys=True),
                    }
                ],
                "structuredContent": payload,
                "isError": result.infrastructure_error is not None,
            },
        }

    def serve(self, input_stream: TextIO, output_stream: TextIO) -> None:
        try:
            for line in input_stream:
                if not line.strip():
                    continue
                try:
                    request = json.loads(line)
                    if not isinstance(request, dict):
                        raise ValueError("request must be an object")
                    response = self.handle(request)
                except (json.JSONDecodeError, ValueError) as exc:
                    response = self._error(None, -32700, str(exc))
                if response is not None:
                    output_stream.write(json.dumps(response, ensure_ascii=True) + "\n")
                    output_stream.flush()
        finally:
            self.executor.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Container-scoped MCP terminal for Codex.")
    parser.add_argument("--container-id", required=True)
    parser.add_argument("--workdir", default="/data/project")
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--command-timeout", type=int, required=True)
    parser.add_argument("--max-output-chars", type=int, default=16000)
    parser.add_argument("--docker", default="docker")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    executor = PersistentContainerShell(
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
