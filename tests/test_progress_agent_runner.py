from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.core.io import write_json
from envsolve_harness.core.models import Case, RunSpec, SolverResult
from envsolve_harness.progress_replay import ACTIVE_PYTHON_MARKER
from envsolve_harness.progress_state import (
    DeploymentCondition,
    ExecutionEvidence,
    ProjectProgressState,
    save_progress_snapshot,
)
from envsolve_harness.runners.free_agent_census import FreeAgentCensusRunner
from envsolve_harness.runners.progress_agent import (
    PROGRESS_METHODS,
    ProgressAgentRunner,
    fork_codex_command,
    progress_session_id,
    validate_progress_identity,
)
from envsolve_harness.storage.artifacts import RunArtifacts


CASE = Case("case", "owner/repo", "a" * 40)


def deployment_condition(identifier: str = "d0") -> DeploymentCondition:
    return DeploymentCondition(
        condition_id=identifier,
        operating_system="linux",
        architecture="arm64",
        python_version="3.11",
        image="envbench:test",
    )


def progress_state() -> ProjectProgressState:
    return ProjectProgressState.start(
        case_id=CASE.case_id,
        repository=CASE.repository,
        revision=CASE.revision,
        program="python -m venv .venv\nsource .venv/bin/activate",
        condition=deployment_condition(),
        evidence=ExecutionEvidence(
            status="pass",
            source="official",
            bootstrap_exit_code=0,
            public_goal_passed=True,
            observed_python="3.11.9",
        ),
    )


def runner(
    root: Path,
    state_path: Path,
    *,
    arm: str = "R0",
    update_state: bool = False,
) -> ProgressAgentRunner:
    return ProgressAgentRunner(
        arm=arm,  # type: ignore[arg-type]
        state_path=state_path,
        target_condition=deployment_condition("d1"),
        source_session_id="session-source" if arm == "R1" else None,
        update_state=update_state,
        state_output_root=root / "states" if update_state else None,
        ssh_target="user@spark",
        remote_workspace_root="/srv/envsolve",
        docker_executable="docker",
        codex_executable=root / "codex",
        harness_root=root,
        source_cache_root=root / "cache",
        image="envbench:test",
        timeout=120,
        command_timeout=30,
        container_create_timeout=10,
        git_fetch_timeout=20,
        goal_contract=ExecutableGoalContract("goal", "fixture", "true"),
    )


def passing_preflight() -> dict[str, Any]:
    return {
        "status": "pass",
        "certified": True,
        "preflight_wall_seconds": 2.5,
        "verification": {
            "bootstrap": {
                "exit_code": 0,
                "duration_seconds": 2,
                "stdout": f"{ACTIVE_PYTHON_MARKER}3.11.9\n",
                "stderr": "",
            }
        },
    }


def test_fork_command_rebinds_supported_options_and_preserves_source() -> None:
    original = [
        "codex",
        "exec",
        "--json",
        "--sandbox",
        "read-only",
        "--cd",
        "/tmp/control",
        "--config",
        "features.shell_tool=false",
        "-",
    ]

    forked = fork_codex_command(original, "session-123")

    assert forked[:3] == ["codex", "exec", "fork"]
    assert "--sandbox" not in forked
    assert "--cd" not in forked
    assert 'sandbox_mode="read-only"' in forked
    assert forked[-2:] == ["session-123", "-"]


def test_session_id_comes_from_thread_started_event() -> None:
    records = [
        {"type": "turn.started"},
        {"type": "thread.started", "thread_id": "new-session"},
    ]

    assert progress_session_id(records) == "new-session"


def test_progress_identity_rejects_a_different_revision() -> None:
    different = Case(CASE.case_id, CASE.repository, "b" * 40)

    with pytest.raises(ValueError, match="does not match"):
        validate_progress_identity(progress_state(), different)


def test_prompts_expose_only_the_information_assigned_to_each_arm(
    tmp_path: Path,
) -> None:
    state = progress_state()
    state_path = tmp_path / "state.json"
    write_json(state_path, state.to_dict())
    preflight = passing_preflight()

    r0 = runner(tmp_path, state_path, arm="R0")
    r0._progress_state = state
    r0._preflight = preflight
    r0_prompt = r0._prompt(CASE, r0.goal_contract)
    assert "ordinary previously successful bootstrap artifact" in r0_prompt
    assert "Progress state version" not in r0_prompt

    p = runner(tmp_path, state_path, arm="P")
    p._progress_state = state
    p._preflight = preflight
    p_prompt = p._prompt(CASE, p.goal_contract)
    assert "Progress state version: 1" in p_prompt
    assert "Latest verified program" in p_prompt

    r1 = runner(tmp_path, state_path, arm="R1")
    r1._progress_state = state
    r1._preflight = preflight
    r1_prompt = r1._prompt(CASE, r1.goal_contract)
    assert "full prior conversation" in r1_prompt
    assert "previous_bootstrap_script" not in r1_prompt


@pytest.mark.parametrize("arm", ["R0", "P"])
def test_passing_preflight_reuses_program_without_model_for_reuse_arms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    arm: str,
) -> None:
    state_root = tmp_path / "input-state"
    state_path = save_progress_snapshot(state_root, progress_state())
    subject = runner(tmp_path, state_path, arm=arm, update_state=True)
    artifacts = RunArtifacts.create(tmp_path / "runs", "run", CASE.case_id)
    write_json(artifacts.manifest, {"solver": None})
    monkeypatch.setattr(
        subject,
        "_preflight_program",
        lambda case, run_artifacts, state: passing_preflight(),
    )

    result = subject.run(
        CASE,
        artifacts,
        RunSpec("run", PROGRESS_METHODS[arm], "gpt-test"),
    )

    assert result.generation_completed is True
    assert result.metadata["project_progress"]["model_invoked"] is False
    assert result.metadata["token_usage"]["input_tokens"] == 0
    assert artifacts.generated_script.read_text(encoding="utf-8").strip() == (
        progress_state().current_program
    )
    output = Path(result.metadata["project_progress"]["state_output_path"])
    assert output.name == "state-v0002.json"


def test_r1_invokes_full_history_agent_even_when_replay_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = save_progress_snapshot(tmp_path / "state", progress_state())
    subject = runner(tmp_path, state_path, arm="R1")
    artifacts = RunArtifacts.create(tmp_path / "runs", "run", CASE.case_id)
    write_json(artifacts.manifest, {"solver": None})
    monkeypatch.setattr(
        subject,
        "_preflight_program",
        lambda case, run_artifacts, state: passing_preflight(),
    )
    calls: list[str] = []

    def fake_agent_run(
        self: FreeAgentCensusRunner,
        case: Case,
        run_artifacts: RunArtifacts,
        run_spec: RunSpec,
    ) -> Any:
        del self, case, run_artifacts
        calls.append(run_spec.method)
        return SolverResult(
            False,
            run_spec.method,
            error="fixture",
            metadata={"process_exit_code": 0},
        )

    monkeypatch.setattr(FreeAgentCensusRunner, "run", fake_agent_run)

    subject.run(
        CASE,
        artifacts,
        RunSpec("run", PROGRESS_METHODS["R1"], "gpt-test"),
    )

    assert calls == [PROGRESS_METHODS["R1"]]
