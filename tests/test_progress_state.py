from __future__ import annotations

from pathlib import Path

import pytest

from envsolve_harness.progress_state import (
    DeploymentCondition,
    ExecutionEvidence,
    ProjectProgressState,
    load_progress_state,
    save_progress_snapshot,
)


def condition(identifier: str, python: str) -> DeploymentCondition:
    return DeploymentCondition(
        condition_id=identifier,
        operating_system="linux",
        architecture="arm64",
        python_version=python,
        image="envbench:test",
    )


def passing(source: str, python: str) -> ExecutionEvidence:
    return ExecutionEvidence(
        status="pass",
        source=source,
        bootstrap_exit_code=0,
        public_goal_passed=True,
        observed_python=python,
        duration_seconds=12.5,
    )


def failing(summary: str) -> ExecutionEvidence:
    return ExecutionEvidence(
        status="fail",
        source="clean-replay",
        bootstrap_exit_code=1,
        public_goal_passed=False,
        failure_summary=summary,
    )


def initial_state() -> ProjectProgressState:
    return ProjectProgressState.start(
        case_id="case",
        repository="owner/repo",
        revision="a" * 40,
        program="python3.11 -m venv .venv\nsource .venv/bin/activate",
        condition=condition("d0", "3.11"),
        evidence=passing("historical-official", "3.11"),
        unresolved_risks=("external downloads can fail transiently",),
    )


def test_successful_repair_updates_program_and_records_executable_delta() -> None:
    state = initial_state()
    updated = state.record(
        condition=condition("d2", "3.10"),
        program="python3.10 -m venv .venv\nsource .venv/bin/activate",
        trigger=failing("observed Python 3.11, required 3.10"),
        evidence=passing("postsession-qualification", "3.10"),
        unresolved_risks=(),
    )

    assert updated.version == 2
    assert updated.current_condition.python_version == "3.10"
    assert "python3.10" in updated.current_program
    assert len(updated.repairs) == 1
    assert "-python3.11" in updated.repairs[0].program_delta
    assert "+python3.10" in updated.repairs[0].program_delta


def test_failed_attempt_leaves_last_successful_program_current() -> None:
    state = initial_state()
    failed = state.record(
        condition=condition("d2", "3.10"),
        program="python3.10 -m venv .venv",
        evidence=failing("package build failed"),
    )

    assert failed.version == 2
    assert failed.current_program == state.current_program
    assert failed.current_condition == state.current_condition
    assert failed.deployments[-1].evidence.status == "fail"


def test_compact_context_contains_state_but_not_raw_trajectory() -> None:
    context = initial_state().compact_context(condition("d2", "3.10"))

    assert "python_version: 3.11 -> 3.10" in context
    assert "<verified_program>" in context
    assert "external downloads can fail transiently" in context
    assert "container-commands.jsonl" not in context


def test_snapshots_are_explicit_and_never_overwritten(tmp_path: Path) -> None:
    state = initial_state()
    path = save_progress_snapshot(tmp_path, state)

    assert path.name == "state-v0001.json"
    assert load_progress_state(path) == state
    with pytest.raises(FileExistsError, match="already exists"):
        save_progress_snapshot(tmp_path, state)


def test_passing_evidence_requires_a_real_goal_pass() -> None:
    with pytest.raises(ValueError, match="passing evidence"):
        ExecutionEvidence(
            status="pass",
            source="fixture",
            bootstrap_exit_code=0,
            public_goal_passed=False,
        )


def test_loaded_current_program_requires_matching_success_evidence() -> None:
    value = initial_state().to_dict()
    value["current_program"] = "echo never-verified"

    with pytest.raises(ValueError, match="matching successful evidence"):
        ProjectProgressState.from_dict(value)
