from __future__ import annotations

import tempfile
from pathlib import Path

from envsolve.runtime import ExecutableGoalContract
from envsolve_harness.core.models import Case, RunSpec
from envsolve_harness.execution.process import checked_output
from envsolve_harness.execution.source_cache import ExactRevisionSourceCache
from envsolve_harness.runners.codex_cli_qualified import (
    QualifiedCodexCliRunner,
    QualifiedEnvSolveProMinimalBRunner,
)


def _kwargs(root: Path) -> dict[str, object]:
    return {
        "codex_executable": root / "codex",
        "harness_root": root,
        "source_cache_root": root / "source-cache",
        "image": "envbench:test",
        "timeout": 120,
        "command_timeout": 30,
        "container_create_timeout": 10,
        "git_fetch_timeout": 20,
        "goal_contract": ExecutableGoalContract(
            contract_id="public-goal",
            description="Synthetic public goal",
            program="true",
        ),
    }


def _make_repository(root: Path) -> tuple[Path, str]:
    repository = root / "remote"
    checked_output(["git", "init", "-q", str(repository)], timeout=10)
    checked_output(
        ["git", "config", "user.email", "envsolve@example.test"],
        cwd=repository,
        timeout=10,
    )
    checked_output(
        ["git", "config", "user.name", "EnvSolve Test"],
        cwd=repository,
        timeout=10,
    )
    (repository / "value.txt").write_text("frozen\n", encoding="utf-8")
    checked_output(["git", "add", "value.txt"], cwd=repository, timeout=10)
    checked_output(["git", "commit", "-q", "-m", "frozen"], cwd=repository, timeout=10)
    revision = checked_output(["git", "rev-parse", "HEAD"], cwd=repository, timeout=10)
    return repository, revision


def test_qualified_control_uses_process_safe_mcp_without_changing_method() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        runner = QualifiedCodexCliRunner(**_kwargs(root))
        arguments = runner._mcp_server_args(
            trace_path=root / "trace.jsonl",
            container_id="container",
            case=Case("case", "owner/repo", "abc"),
            image_digest="sha256:image",
        )

    assert runner._goal_contract_for_run(
        RunSpec("run", "codex-cli-goal-aware", "gpt-5.5")
    ) is not None
    assert "envsolve_harness.codex.container_mcp_qualified" in arguments


def test_qualified_minimal_b_uses_same_infrastructure_layer() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        runner = QualifiedEnvSolveProMinimalBRunner(**_kwargs(root))
        arguments = runner._mcp_server_args(
            trace_path=root / "generation" / "container-commands.jsonl",
            container_id="container",
            case=Case("case", "owner/repo", "abc"),
            image_digest="sha256:image",
        )

    assert "envsolve_harness.codex.minimal_b_mcp_qualified" in arguments
    assert runner.infrastructure_profile == "codex-qualified-infrastructure-v1"


def test_qualified_runner_reuses_objects_without_reusing_agent_state() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        remote, revision = _make_repository(root)
        repository = "owner/repository"
        cache = ExactRevisionSourceCache(root / "source-cache", timeout=10)
        first = cache.acquire(
            repository=repository,
            revision=revision,
            destination=root / "first",
            remote_url=str(remote),
        )
        (root / "first" / "agent-state.txt").write_text("private\n", encoding="utf-8")

        runner = QualifiedCodexCliRunner(**_kwargs(root))
        second = runner._acquire_repository(
            Case("case", repository, revision),
            root / "second",
        )

        assert first["cache_hit"] is False
        assert second["cache_hit"] is True
        assert second["commit"] == revision
        assert not (root / "second" / "agent-state.txt").exists()
