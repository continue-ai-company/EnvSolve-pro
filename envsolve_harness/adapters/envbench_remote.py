from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any

from envsolve_harness.execution.batch import cleanup_case_containers
from envsolve_harness.execution.remote_docker import SshDockerTransport


_REMOTE_EVALUATION_SCRIPT = r"""
set -euo pipefail
benchmark_root=$1
budget_seconds=$2
shift 2
cd "$benchmark_root"
exec timeout --foreground --signal=TERM --kill-after=30s "${budget_seconds}s" "$@"
""".strip()


class RemoteEnvBenchProcessRunner:
    """Run the complete EnvBench evaluator on one SSH execution host."""

    def __init__(
        self,
        *,
        transport: SshDockerTransport,
        local_benchmark_root: Path,
        remote_benchmark_root: str,
        local_benchmark_input: Path,
        local_json_results: Path,
        local_repo_data: Path,
        local_temp_dir: Path,
        remote_run_root: str,
        image: str,
        sync_timeout: int,
    ) -> None:
        self.transport = transport
        self.local_benchmark_root = local_benchmark_root.resolve()
        self.remote_benchmark_root = self._remote_path(remote_benchmark_root)
        self.local_benchmark_input = local_benchmark_input.resolve()
        self.local_json_results = local_json_results.resolve()
        self.local_repo_data = local_repo_data.resolve()
        self.local_temp_dir = local_temp_dir.resolve()
        self.remote_run_root = self._remote_path(remote_run_root)
        self.image = image
        self.sync_timeout = sync_timeout
        remote_root = PurePosixPath(self.remote_run_root)
        self.remote_input_root = str(remote_root / "inputs")
        self.remote_benchmark_input = str(
            PurePosixPath(self.remote_input_root) / self.local_benchmark_input.name
        )
        self.remote_json_results = str(remote_root / "json")
        self.remote_repo_data = str(remote_root / "repos")
        self.remote_temp_dir = str(remote_root / "tmp")
        self.execution_metadata: dict[str, Any] = {
            "kind": "ssh-remote-envbench",
            "ssh_target": self.transport.target,
            "remote_benchmark_root": self.remote_benchmark_root,
            "remote_run_root": self.remote_run_root,
            "controller_role": "control-and-artifact-storage-only",
            "execution_host_role": (
                "construction-replay-qualification-and-official"
            ),
        }

    @staticmethod
    def _remote_path(value: str) -> str:
        path = PurePosixPath(value)
        if not path.is_absolute() or ".." in path.parts:
            raise ValueError("Remote EnvBench paths must be absolute and normalized")
        return str(path)

    def _probe(self, command: list[str]) -> str | None:
        try:
            return self.transport.checked_remote(command, timeout=self.sync_timeout)
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            return None

    def _collect_provenance(self) -> None:
        status = self._probe(
            ["git", "-C", self.remote_benchmark_root, "status", "--porcelain"]
        )
        source_hashes: dict[str, str | None] = {}
        for name, relative in (
            ("main.py", "evaluation/main.py"),
            ("python_build.sh", "evaluation/scripts/python_build.sh"),
            ("repo_downloader.py", "env_setup_utils/repo_downloader.py"),
        ):
            output = self._probe(
                ["sha256sum", str(PurePosixPath(self.remote_benchmark_root) / relative)]
            )
            source_hashes[name] = output.split()[0] if output else None
        repo_digests_text = self._probe(
            [
                self.transport.docker_executable,
                "image",
                "inspect",
                "--format",
                "{{json .RepoDigests}}",
                self.image,
            ]
        )
        try:
            repo_digests = json.loads(repo_digests_text or "[]")
        except json.JSONDecodeError:
            repo_digests = []
        self.execution_metadata.update(
            {
                "hostname": self._probe(["hostname"]),
                "kernel": self._probe(["uname", "-s"]),
                "architecture": self._probe(["uname", "-m"]),
                "benchmark": {
                    "path": self.remote_benchmark_root,
                    "revision": self._probe(
                        [
                            "git",
                            "-C",
                            self.remote_benchmark_root,
                            "rev-parse",
                            "HEAD",
                        ]
                    ),
                    "dirty": bool(status) if status is not None else None,
                    "status": status.splitlines() if status else [],
                    "source_hashes": source_hashes,
                },
                "docker": {
                    "context": self._probe(
                        [self.transport.docker_executable, "context", "show"]
                    ),
                    "server_architecture": self._probe(
                        [
                            self.transport.docker_executable,
                            "version",
                            "--format",
                            "{{.Server.Arch}}",
                        ]
                    ),
                    "server_os": self._probe(
                        [
                            self.transport.docker_executable,
                            "version",
                            "--format",
                            "{{.Server.Os}}",
                        ]
                    ),
                    "daemon_name": self._probe(
                        [
                            self.transport.docker_executable,
                            "info",
                            "--format",
                            "{{.Name}}",
                        ]
                    ),
                    "root_dir": self._probe(
                        [
                            self.transport.docker_executable,
                            "info",
                            "--format",
                            "{{.DockerRootDir}}",
                        ]
                    ),
                    "networks": (
                        self._probe(
                            [
                                self.transport.docker_executable,
                                "network",
                                "ls",
                                "--format",
                                "{{.Name}}|{{.Driver}}|{{.Scope}}",
                            ]
                        )
                        or ""
                    ).splitlines(),
                },
                "image": {
                    "reference": self.image,
                    "id": self._probe(
                        [
                            self.transport.docker_executable,
                            "image",
                            "inspect",
                            "--format",
                            "{{.Id}}",
                            self.image,
                        ]
                    ),
                    "repo_digests": repo_digests,
                },
            }
        )

    @staticmethod
    def _rewrite_argument(argument: str, mapping: dict[Path, str]) -> str:
        prefix, separator, value = argument.partition("=")
        candidate = value if separator else argument
        try:
            resolved = Path(candidate).resolve()
        except OSError:
            return argument
        for local, remote in mapping.items():
            if resolved == local:
                return f"{prefix}={remote}" if separator else remote
        return argument

    def _prepare_remote_tree(self) -> None:
        created = self.transport.run_remote(
            [
                "mkdir",
                "-p",
                self.remote_run_root,
                self.remote_input_root,
                self.remote_json_results,
                self.remote_repo_data,
                self.remote_temp_dir,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=self.sync_timeout,
        )
        if created.returncode != 0:
            detail = created.stderr.strip() or created.stdout.strip()
            raise OSError(f"Unable to create remote EnvBench tree: {detail}")
        self.transport.sync_to_remote(
            self.local_benchmark_input.parent,
            self.remote_input_root,
            timeout=self.sync_timeout,
        )
        self.transport.sync_to_remote(
            self.local_repo_data,
            self.remote_repo_data,
            timeout=self.sync_timeout,
        )

    def _sync_results(self) -> None:
        self.transport.sync_from_remote(
            self.remote_json_results,
            self.local_json_results,
            timeout=self.sync_timeout,
        )

    def __call__(
        self,
        command: list[str],
        *,
        cwd: Path,
        timeout: int,
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[str]:
        if cwd.resolve() != self.local_benchmark_root:
            raise ValueError("Remote EnvBench runner received an unexpected benchmark root")
        self._collect_provenance()
        self._prepare_remote_tree()
        mapping = {
            self.local_benchmark_input: self.remote_benchmark_input,
            self.local_json_results: self.remote_json_results,
            self.local_repo_data: self.remote_repo_data,
            self.local_temp_dir: self.remote_temp_dir,
        }
        rewritten = [self._rewrite_argument(item, mapping) for item in command]
        remote_command = [
            "/bin/bash",
            "-lc",
            _REMOTE_EVALUATION_SCRIPT,
            "--",
            self.remote_benchmark_root,
            str(timeout),
            "/usr/bin/env",
            (
                "ENVBENCH_GIT_FETCH_TIMEOUT_SECONDS="
                + env.get("ENVBENCH_GIT_FETCH_TIMEOUT_SECONDS", "300")
            ),
            *rewritten,
        ]
        try:
            process = self.transport.run_remote(
                remote_command,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout + 45,
            )
        except subprocess.TimeoutExpired as exc:
            try:
                self._sync_results()
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                pass
            raise subprocess.TimeoutExpired(
                command,
                timeout,
                output=exc.stdout,
                stderr=exc.stderr,
            ) from exc
        try:
            self._sync_results()
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            raise OSError(f"Unable to retrieve remote EnvBench results: {exc}") from exc
        if process.returncode in {124, 137}:
            raise subprocess.TimeoutExpired(
                command,
                timeout,
                output=process.stdout,
                stderr=process.stderr,
            )
        if process.returncode == 255:
            raise OSError(
                "Remote EnvBench SSH execution failed: "
                + (process.stderr.strip() or process.stdout.strip())
            )
        return subprocess.CompletedProcess(
            command,
            process.returncode,
            process.stdout,
            process.stderr,
        )

    def cleanup_containers(self, _: Path) -> tuple[str, ...]:
        def remote_docker(
            command: list[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            if not command or Path(command[0]).name != "docker":
                raise ValueError("Remote cleanup accepts Docker commands only")
            return self.transport.run_docker(command[1:], **kwargs)

        return cleanup_case_containers(
            Path(self.remote_run_root),
            run_command=remote_docker,
        )

    def cleanup_staging(self) -> None:
        process = self.transport.run_remote(
            ["rm", "-rf", self.remote_run_root],
            capture_output=True,
            text=True,
            check=False,
            timeout=self.sync_timeout,
        )
        if process.returncode == 0:
            self.execution_metadata["staging_cleaned"] = True
            return

        initial_error = process.stderr.strip() or process.stdout.strip()
        container_cleanup = self.transport.run_docker(
            [
                "run",
                "--rm",
                "--mount",
                f"type=bind,src={self.remote_run_root},dst=/envsolve-staging",
                "--entrypoint",
                "/usr/bin/find",
                self.image,
                "/envsolve-staging",
                "-mindepth",
                "1",
                "-delete",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=self.sync_timeout,
        )
        if container_cleanup.returncode == 0:
            remove_root = self.transport.run_remote(
                ["rmdir", self.remote_run_root],
                capture_output=True,
                text=True,
                check=False,
                timeout=self.sync_timeout,
            )
            if remove_root.returncode == 0:
                self.execution_metadata.update(
                    {
                        "staging_cleaned": True,
                        "staging_cleanup_fallback": "docker-root-owned-content",
                    }
                )
                return
            fallback_error = remove_root.stderr.strip() or remove_root.stdout.strip()
        else:
            fallback_error = (
                container_cleanup.stderr.strip() or container_cleanup.stdout.strip()
            )
        self.execution_metadata["staging_cleanup_error"] = (
            f"ordinary removal failed: {initial_error}; "
            f"container fallback failed: {fallback_error}"
        )
