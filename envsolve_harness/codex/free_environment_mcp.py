"""Agent-directed container lifecycle, without a verifier or repair policy."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any, Callable
import uuid

from envsolve.runtime.workspace import WorkspacePrecondition
from envsolve_harness.codex.container_mcp import ContainerMcpServer, _bounded_output, _now
from envsolve_harness.execution.remote_docker import SshDockerTransport


class FreeEnvironmentPool:
    def __init__(
        self,
        *,
        transport: SshDockerTransport,
        source_cache: str,
        revision: str,
        image: str,
        root: str,
        timeout: int,
        workspace_dirs: tuple[str, ...] = (),
        expose_gpus: bool = False,
    ) -> None:
        self.transport = transport
        self.source_cache = source_cache
        self.revision = revision
        self.image = image
        self.root = PurePosixPath(root)
        self.timeout = timeout
        self.workspace_dirs = tuple(WorkspacePrecondition(p).path for p in workspace_dirs)
        self.expose_gpus = expose_gpus
        self.environments: dict[str, dict[str, str]] = {}

    def create(self) -> dict[str, str]:
        environment_id = uuid.uuid4().hex
        path = str(self.root / environment_id)
        name = f"envsolve-free-{environment_id}"
        record = {
            "environment_id": environment_id,
            "container_id": name,
            "source_path": path,
            "workdir": "/data/project",
            "image": self.image,
            "revision": self.revision,
        }
        self.environments[environment_id] = record
        t = self.transport
        try:
            t.checked_remote(["mkdir", "-p", str(self.root)], timeout=self.timeout)
            t.checked_remote(
                [
                    "env",
                    "GIT_LFS_SKIP_SMUDGE=1",
                    "git",
                    "clone",
                    "--quiet",
                    "--no-hardlinks",
                    "--no-checkout",
                    self.source_cache,
                    path,
                ],
                timeout=self.timeout,
            )
            t.checked_remote(
                [
                    "env",
                    "GIT_LFS_SKIP_SMUDGE=1",
                    "git",
                    "-C",
                    path,
                    "checkout",
                    "--quiet",
                    "--detach",
                    self.revision,
                ],
                timeout=self.timeout,
            )
            for directory in self.workspace_dirs:
                t.checked_remote(
                    ["mkdir", "-p", str(PurePosixPath(path) / directory)],
                    timeout=self.timeout,
                )
            command = [
                "create",
                "--name",
                name,
                "--init",
                "--entrypoint",
                "/bin/bash",
                "--mount",
                f"type=bind,src={path},dst=/data/project",
                "--workdir",
                "/data/project",
            ]
            if self.expose_gpus:
                command += ["--gpus", "all"]
            startup = "exec sleep infinity"
            if t.requires_bind_mount_chown(timeout=self.timeout):
                startup = "chmod -R 777 /data/project && exec sleep infinity"
            command += [self.image, "-c", startup]
            t.checked_docker(command, timeout=self.timeout)
            t.checked_docker(["start", name], timeout=self.timeout)
            t.checked_docker(
                ["exec", name, "test", "-d", "/data/project/.git"],
                timeout=self.timeout,
            )
            return dict(record)
        except Exception as original:
            # Keep ownership information if cleanup itself fails.
            try:
                self.close(environment_id)
            except Exception as cleanup:
                raise RuntimeError(f"Create failed: {original}; cleanup failed: {cleanup}") from original
            raise

    def close(self, environment_id: str) -> None:
        record = self.environments[environment_id]
        result = self.transport.run_docker(
            ["rm", "-f", record["container_id"]],
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if result.returncode and "No such container" not in result.stderr:
            raise RuntimeError(f"Container cleanup failed: {result.stderr.strip()}")
        exists = self.transport.run_remote(
            ["test", "-d", record["source_path"]],
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if exists.returncode == 0:
            if self.transport.requires_bind_mount_chown(timeout=self.timeout):
                # Container-created files can be root-owned on a Linux bind mount.
                self.transport.checked_docker(
                    [
                        "run",
                        "--rm",
                        "--network",
                        "none",
                        "--user",
                        "0:0",
                        "--mount",
                        f"type=bind,src={record['source_path']},dst=/data/project",
                        "--entrypoint",
                        "/bin/chmod",
                        self.image,
                        "-R",
                        "a+rwX",
                        "/data/project",
                    ],
                    timeout=self.timeout,
                )
        elif exists.returncode != 1:
            raise RuntimeError(f"Workspace cleanup inspection failed: {exists.stderr.strip()}")
        self.transport.checked_remote(["rm", "-rf", record["source_path"]], timeout=self.timeout)
        del self.environments[environment_id]


class FreeEnvironmentMcpServer(ContainerMcpServer):
    def __init__(
        self,
        executor: Any,
        trace_path: Path,
        pool: FreeEnvironmentPool,
        shell_factory: Callable[[str], Any],
    ) -> None:
        super().__init__(executor, trace_path)
        self.pool = pool
        self.shell_factory = shell_factory
        self.servers: dict[str, ContainerMcpServer] = {}

    def _lifecycle(self, payload: dict[str, Any]) -> None:
        path = self.trace_path.with_name("environment-lifecycle.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as stream:
            stream.write(json.dumps({"recorded_at": _now(), **payload}, sort_keys=True) + "\n")

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        method = request.get("method")
        if method == "tools/list":
            response = super().handle(request)
            tools = response["result"]["tools"]
            tools[0]["inputSchema"]["properties"]["environment_id"] = {
                "type": "string",
                "description": (
                    "Omit for construction; otherwise use an ID returned by "
                    "envbench_environment."
                ),
            }
            tools.append(
                {
                    "name": "envbench_environment",
                    "description": (
                        "Create an independent exact-revision checkout in a fresh "
                        "base container, or close it. No program or verifier runs "
                        "automatically. Use envbench_shell with its ID for arbitrary "
                        "commands."
                    ),
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["create", "close"],
                            },
                            "environment_id": {"type": "string"},
                        },
                        "required": ["action"],
                        "additionalProperties": False,
                    },
                }
            )
            return response
        params = request.get("params", {})
        if method != "tools/call" or not isinstance(params, dict):
            return super().handle(request)
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            return self._error(request.get("id"), -32602, "arguments must be an object")
        if params.get("name") == "envbench_shell" and "environment_id" in arguments:
            identity = arguments["environment_id"]
            if not isinstance(identity, str) or identity not in self.pool.environments:
                return self._error(request.get("id"), -32602, "unknown environment_id")
            if identity not in self.servers:
                shell = self.shell_factory(self.pool.environments[identity]["container_id"])
                path = self.trace_path.with_name(f"environment-{identity}-commands.jsonl")
                self.servers[identity] = ContainerMcpServer(shell, path)
            routed_request = {
                **request,
                "params": {
                    **params,
                    "arguments": {
                        name: value
                        for name, value in arguments.items()
                        if name != "environment_id"
                    },
                },
            }
            return self.servers[identity].handle(routed_request)
        if params.get("name") != "envbench_environment":
            return super().handle(request)
        action = arguments.get("action")
        identity = arguments.get("environment_id")
        if not isinstance(action, str) or action not in {"create", "close"}:
            return self._error(request.get("id"), -32602, "action must be create or close")
        if action == "create" and identity is not None:
            return self._error(
                request.get("id"),
                -32602,
                "environment_id is only valid when closing an environment",
            )
        if action == "close" and (not isinstance(identity, str) or identity not in self.pool.environments):
            return self._error(request.get("id"), -32602, "unknown environment_id")
        try:
            if action == "create":
                payload = {"action": action, **self.pool.create()}
            else:
                if identity in self.servers:
                    self.servers.pop(identity).executor.close()
                self.pool.close(identity)
                payload = {"action": action, "environment_id": identity}
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            message, truncated = _bounded_output(f"{type(exc).__name__}: {exc}", 16000)
            payload = {"action": action, "error": message, "error_truncated": truncated}
        self._lifecycle(payload)
        return {"jsonrpc": "2.0", "id": request.get("id"), "result": {
            "content": [{"type": "text", "text": json.dumps(payload)}],
            "structuredContent": payload, "isError": "error" in payload}}

    def serve(self, input_stream: Any, output_stream: Any) -> None:
        try:
            super().serve(input_stream, output_stream)
        finally:
            for server in self.servers.values():
                server.executor.close()
            errors = []
            for identity in list(self.pool.environments):
                try:
                    self.pool.close(identity)
                except Exception as exc:
                    errors.append({"environment_id": identity, "error": str(exc)})
            self._lifecycle({"action": "session_cleanup", "errors": errors})
