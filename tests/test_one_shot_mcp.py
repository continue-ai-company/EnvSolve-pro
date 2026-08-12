from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from envsolve.runtime.docker import DockerFreshEnvironmentProvider
from envsolve.solver import (
    CommandResult,
    CounterexampleEvidence,
    DeploymentCandidate,
    EnvironmentReceipt,
    ExecutableVerification,
    FeedbackChannel,
    ProvisionedEnvironment,
)
from envsolve_harness.codex.container_mcp import ContainerCommandResult
from envsolve_harness.codex.one_shot_mcp import (
    OneShotCleanReplayService,
    OneShotMinimalBMcpServer,
)
from envsolve_harness.core.io import read_json, read_jsonl


class _Provider:
    def __init__(self) -> None:
        self.provisioned = 0
        self.released = 0

    def provision(self, candidate: DeploymentCandidate) -> ProvisionedEnvironment:
        self.provisioned += 1
        return ProvisionedEnvironment(
            EnvironmentReceipt(
                f"fresh-{self.provisioned}",
                "fake-provider",
                "sha256:image",
                "owner/repo",
                "abc123",
                "2026-08-05T00:00:00+00:00",
            ),
            handle=f"fresh-{self.provisioned}",
        )

    def release(self, environment: ProvisionedEnvironment) -> None:
        self.released += 1


class _FailingVerifier:
    def verify(
        self,
        candidate: DeploymentCandidate,
        environment: ProvisionedEnvironment,
    ) -> ExecutableVerification:
        return ExecutableVerification(
            verifier="fake-public-goal",
            check_profile="fake-v1",
            channel=FeedbackChannel.INTERNAL_EXECUTION,
            passed=False,
            bootstrap=CommandResult(0, stdout="one finding"),
            summary="one finding remains",
            counterexamples=(
                CounterexampleEvidence("module-requirement", {"name": "demo"}),
            ),
        )


class _Executor:
    def execute(
        self,
        command: str,
        timeout_seconds: int | None = None,
    ) -> ContainerCommandResult:
        return ContainerCommandResult(command, 0, "ok", 0.01)

    def close(self) -> None:
        return None


def _service(root: Path) -> tuple[OneShotCleanReplayService, _Provider]:
    provider = _Provider()
    return (
        OneShotCleanReplayService(
            provider=provider,
            verifier=_FailingVerifier(),
            repository="owner/repo",
            revision="abc123",
            image_digest="sha256:image",
            goal_contract_sha256="goal-sha256",
            trace_path=root / "replays.jsonl",
            certification_path=root / "certification.json",
            programs_root=root / "programs",
        ),
        provider,
    )


def test_one_shot_executes_only_the_first_replay_submission() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        service, provider = _service(root)

        first = service.submit("true")
        second = service.submit("export READY=1")

        assert first["status"] == "fail"
        assert second["status"] == "replay_limit"
        assert second["replay_executed"] is False
        assert provider.provisioned == provider.released == 1
        assert read_json(root / "certification.json")["replay_count"] == 1
        assert [item["status"] for item in read_jsonl(root / "replays.jsonl")] == [
            "fail",
            "replay_limit",
        ]


def test_one_shot_mcp_advertises_limit_and_marks_second_call_as_error() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        service, _ = _service(root)
        server = OneShotMinimalBMcpServer(
            _Executor(),
            root / "commands.jsonl",
            service,
        )
        initialized = server.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        tools = server.handle(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        )
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "submit_and_replay",
                "arguments": {"program": "true"},
            },
        }
        server.handle({"id": 3, **request})
        rejected = server.handle({"id": 4, **request})

        assert initialized["result"]["serverInfo"]["version"] == "1.0.0"
        replay_tool = tools["result"]["tools"][1]
        assert "Exactly once" in replay_tool["description"]
        assert rejected["result"]["structuredContent"]["status"] == "replay_limit"
        assert rejected["result"]["isError"] is True


@pytest.mark.skipif(
    os.environ.get("ENVSOLVE_ONE_SHOT_DOCKER_TEST") != "1",
    reason="set ENVSOLVE_ONE_SHOT_DOCKER_TEST=1 to run Docker integration",
)
def test_one_shot_does_not_provision_a_second_real_container() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        repository = root / "repository"
        subprocess.run(["git", "init", "-q", str(repository)], check=True)
        subprocess.run(
            ["git", "config", "user.email", "envsolve@example.test"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "EnvSolve Test"],
            cwd=repository,
            check=True,
        )
        (repository / "README.md").write_text("one shot\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "initial"],
            cwd=repository,
            check=True,
        )
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        image = "ghcr.io/jetbrains-research/envbench-python:latest"
        image_digest = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", image],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        provider = DockerFreshEnvironmentProvider(
            source_repository=repository,
            worktrees_root=root / "worktrees",
            repository="owner/repo",
            revision=revision,
            image=image_digest,
            create_timeout=300,
        )
        service = OneShotCleanReplayService(
            provider=provider,
            verifier=_FailingVerifier(),
            repository="owner/repo",
            revision=revision,
            image_digest=image_digest,
            goal_contract_sha256="goal-sha256",
            trace_path=root / "replays.jsonl",
            certification_path=root / "certification.json",
            programs_root=root / "programs",
        )

        first = service.submit("true")
        second = service.submit("export READY=1")
        records = read_jsonl(root / "replays.jsonl")

        assert first["status"] == "fail"
        assert second["status"] == "replay_limit"
        assert sum("environment_receipt" in item for item in records) == 1
