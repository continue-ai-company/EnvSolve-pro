from __future__ import annotations

from pathlib import Path

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.core.models import Case, RunSpec
from envsolve_harness.runners.certification_repair_boundary_v6 import CONTROL_METHOD
from envsolve_harness.runners.v7_persistent_codex import (
    V7PersistentP0RemoteCodexRunner,
)


def _runner(root: Path) -> V7PersistentP0RemoteCodexRunner:
    return V7PersistentP0RemoteCodexRunner(
        codex_executable=root / "codex",
        harness_root=root,
        source_cache_root=root / "cache",
        image="sha256:fixture",
        timeout=100,
        command_timeout=20,
        container_create_timeout=10,
        git_fetch_timeout=10,
        goal_contract=ExecutableGoalContract("goal-v7", "Fixture", "true"),
        ssh_target="agenthub@host",
        remote_workspace_root="/tmp/envsolve-v7",
    )


def test_p0_is_persistent_and_retains_the_public_goal(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    run_spec = RunSpec("p0", CONTROL_METHOD, "gpt-5.6-sol")
    command = runner._codex_command(
        run_spec=run_spec,
        control_dir=tmp_path / "control",
        schema_path=tmp_path / "schema.json",
        output_path=tmp_path / "output.json",
        trace_path=tmp_path / "trace.jsonl",
        container_id="container",
        case=Case("fixture", "org/repo", "a" * 40),
        image_digest="sha256:fixture",
    )

    assert "--ephemeral" not in command
    assert command[:3] == [str(tmp_path / "codex"), "exec", "--json"]
    assert runner._goal_contract_for_run(run_spec) is runner.goal_contract

