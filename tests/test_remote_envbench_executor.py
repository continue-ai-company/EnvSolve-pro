from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
from typing import Any

from envsolve_harness.adapters.envbench_remote import RemoteEnvBenchProcessRunner
from envsolve_harness.core.io import write_jsonl


class _FakeTransport:
    target = "runner@example"
    docker_executable = "docker"

    def __init__(self) -> None:
        self.remote_calls: list[list[str]] = []
        self.uploads: list[tuple[Path, str]] = []
        self.downloads: list[tuple[str, Path]] = []

    def checked_remote(self, command: list[str], *, timeout: int) -> str:
        del timeout
        values = {
            ("hostname",): "spark",
            ("uname", "-s"): "Linux",
            ("uname", "-m"): "aarch64",
            ("git", "-C", "/srv/EnvBench", "status", "--porcelain"): "",
            ("git", "-C", "/srv/EnvBench", "rev-parse", "HEAD"): "abc123",
            ("sha256sum", "/srv/EnvBench/evaluation/main.py"): "mainhash  main.py",
            (
                "sha256sum",
                "/srv/EnvBench/evaluation/scripts/python_build.sh",
            ): "buildhash  python_build.sh",
            (
                "sha256sum",
                "/srv/EnvBench/env_setup_utils/repo_downloader.py",
            ): "repohash  repo_downloader.py",
            ("docker", "context", "show"): "default",
            ("docker", "version", "--format", "{{.Server.Arch}}"): "arm64",
            ("docker", "version", "--format", "{{.Server.Os}}"): "linux",
            ("docker", "info", "--format", "{{.Name}}"): "spark",
            ("docker", "info", "--format", "{{.DockerRootDir}}"): "/var/lib/docker",
            (
                "docker",
                "network",
                "ls",
                "--format",
                "{{.Name}}|{{.Driver}}|{{.Scope}}",
            ): "bridge|bridge|local",
            (
                "docker",
                "image",
                "inspect",
                "--format",
                "{{.Id}}",
                "envbench:test",
            ): "sha256:image",
            (
                "docker",
                "image",
                "inspect",
                "--format",
                "{{json .RepoDigests}}",
                "envbench:test",
            ): '["envbench@test"]',
        }
        return values[tuple(command)]

    def run_remote(
        self, command: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        self.remote_calls.append(command)
        return subprocess.CompletedProcess(command, 0, "remote stdout", "")

    def run_docker(
        self, arguments: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        return self.run_remote([self.docker_executable, *arguments], **kwargs)

    def sync_to_remote(
        self, local: Path, remote: str, *, timeout: int
    ) -> None:
        del timeout
        self.uploads.append((local, remote))

    def sync_from_remote(
        self,
        remote: str,
        local: Path,
        *,
        timeout: int,
        excludes: tuple[str, ...] = (),
    ) -> None:
        del timeout, excludes
        self.downloads.append((remote, local))
        write_jsonl(
            local / "results.jsonl",
            [
                {
                    "repo_name": "owner/repo",
                    "commit_sha": "abc",
                    "exit_code": 0,
                    "issues_count": 0,
                    "pyright": {"summary": {"errorCount": 0}},
                }
            ],
        )


def test_remote_envbench_rewrites_all_evaluator_paths_and_records_host() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        benchmark = root / "EnvBench"
        benchmark.mkdir()
        inputs = root / "case" / "inputs"
        inputs.mkdir(parents=True)
        benchmark_input = inputs / "evaluator.jsonl"
        benchmark_input.write_text("{}\n", encoding="utf-8")
        json_results = root / "case" / "evaluation" / "json"
        repo_data = root / "case" / "evaluation" / "repos"
        temp_dir = root / "case" / "evaluation" / "tmp"
        for path in (json_results, repo_data, temp_dir):
            path.mkdir(parents=True)
        transport = _FakeTransport()
        runner = RemoteEnvBenchProcessRunner(
            transport=transport,  # type: ignore[arg-type]
            local_benchmark_root=benchmark,
            remote_benchmark_root="/srv/EnvBench",
            local_benchmark_input=benchmark_input,
            local_json_results=json_results,
            local_repo_data=repo_data,
            local_temp_dir=temp_dir,
            remote_run_root="/srv/runs/official-1",
            image="envbench:test",
            sync_timeout=30,
        )
        command = [
            "uv",
            "run",
            "python",
            "evaluation/main.py",
            f"input.local={benchmark_input}",
            f"operation.dirs.json_results={json_results}",
            f"operation.dirs.repo_data={repo_data}",
            f"operation.dirs.tmp={temp_dir}",
        ]
        process = runner(
            command,
            cwd=benchmark,
            timeout=60,
            env={"ENVBENCH_GIT_FETCH_TIMEOUT_SECONDS": "20"},
        )
        result_exists = (json_results / "results.jsonl").is_file()

    assert process.returncode == 0
    evaluation_call = next(call for call in transport.remote_calls if "uv" in call)
    serialized = " ".join(evaluation_call)
    assert str(root) not in serialized
    assert "input.local=/srv/runs/official-1/inputs/evaluator.jsonl" in serialized
    assert "operation.dirs.json_results=/srv/runs/official-1/json" in serialized
    assert "operation.dirs.repo_data=/srv/runs/official-1/repos" in serialized
    assert "operation.dirs.tmp=/srv/runs/official-1/tmp" in serialized
    assert runner.execution_metadata["hostname"] == "spark"
    assert runner.execution_metadata["architecture"] == "aarch64"
    assert runner.execution_metadata["docker"]["context"] == "default"
    assert runner.execution_metadata["image"]["id"] == "sha256:image"
    assert result_exists


def test_remote_envbench_timeout_is_reported_as_timeout() -> None:
    class TimeoutTransport(_FakeTransport):
        def run_remote(
            self, command: list[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            del kwargs
            self.remote_calls.append(command)
            if "uv" in command:
                return subprocess.CompletedProcess(command, 124, "partial", "timed out")
            return subprocess.CompletedProcess(command, 0, "", "")

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        benchmark = root / "EnvBench"
        benchmark.mkdir()
        benchmark_input = root / "inputs" / "evaluator.jsonl"
        benchmark_input.parent.mkdir()
        benchmark_input.write_text("{}\n", encoding="utf-8")
        paths = [root / name for name in ("json", "repos", "tmp")]
        for path in paths:
            path.mkdir()
        runner = RemoteEnvBenchProcessRunner(
            transport=TimeoutTransport(),  # type: ignore[arg-type]
            local_benchmark_root=benchmark,
            remote_benchmark_root="/srv/EnvBench",
            local_benchmark_input=benchmark_input,
            local_json_results=paths[0],
            local_repo_data=paths[1],
            local_temp_dir=paths[2],
            remote_run_root="/srv/runs/official-timeout",
            image="envbench:test",
            sync_timeout=30,
        )
        try:
            runner(
                ["uv", "run", "python", "evaluation/main.py"],
                cwd=benchmark,
                timeout=60,
                env={},
            )
        except subprocess.TimeoutExpired as exc:
            assert exc.timeout == 60
        else:
            raise AssertionError("remote timeout was not surfaced")


def _cleanup_runner(transport: _FakeTransport) -> RemoteEnvBenchProcessRunner:
    root = Path("/tmp/local-envsolve-cleanup-test")
    return RemoteEnvBenchProcessRunner(
        transport=transport,  # type: ignore[arg-type]
        local_benchmark_root=root / "EnvBench",
        remote_benchmark_root="/srv/EnvBench",
        local_benchmark_input=root / "inputs/evaluator.jsonl",
        local_json_results=root / "json",
        local_repo_data=root / "repos",
        local_temp_dir=root / "tmp",
        remote_run_root="/srv/runs/official-cleanup",
        image="envbench:test",
        sync_timeout=30,
    )


def test_remote_envbench_staging_cleanup_uses_ordinary_removal() -> None:
    transport = _FakeTransport()
    runner = _cleanup_runner(transport)

    runner.cleanup_staging()

    assert runner.execution_metadata["staging_cleaned"] is True
    assert "staging_cleanup_fallback" not in runner.execution_metadata
    assert transport.remote_calls == [
        ["rm", "-rf", "/srv/runs/official-cleanup"]
    ]


def test_remote_envbench_staging_cleanup_handles_root_owned_content() -> None:
    class RootOwnedTransport(_FakeTransport):
        def run_remote(
            self, command: list[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            del kwargs
            self.remote_calls.append(command)
            if command[:2] == ["rm", "-rf"]:
                return subprocess.CompletedProcess(
                    command, 1, "", "Permission denied"
                )
            return subprocess.CompletedProcess(command, 0, "", "")

    transport = RootOwnedTransport()
    runner = _cleanup_runner(transport)

    runner.cleanup_staging()

    assert runner.execution_metadata["staging_cleaned"] is True
    assert (
        runner.execution_metadata["staging_cleanup_fallback"]
        == "docker-root-owned-content"
    )
    assert transport.remote_calls[1] == [
        "docker",
        "run",
        "--rm",
        "--mount",
        "type=bind,src=/srv/runs/official-cleanup,dst=/envsolve-staging",
        "--entrypoint",
        "/usr/bin/find",
        "envbench:test",
        "/envsolve-staging",
        "-mindepth",
        "1",
        "-delete",
    ]
    assert transport.remote_calls[2] == [
        "rmdir",
        "/srv/runs/official-cleanup",
    ]


def test_remote_envbench_staging_cleanup_records_fallback_failure() -> None:
    class FailedCleanupTransport(_FakeTransport):
        def run_remote(
            self, command: list[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            del kwargs
            self.remote_calls.append(command)
            if command[:2] == ["rm", "-rf"]:
                return subprocess.CompletedProcess(
                    command, 1, "", "Permission denied"
                )
            return subprocess.CompletedProcess(command, 125, "", "Docker failed")

    runner = _cleanup_runner(FailedCleanupTransport())

    runner.cleanup_staging()

    assert "staging_cleaned" not in runner.execution_metadata
    assert runner.execution_metadata["staging_cleanup_error"] == (
        "ordinary removal failed: Permission denied; "
        "container fallback failed: Docker failed"
    )
