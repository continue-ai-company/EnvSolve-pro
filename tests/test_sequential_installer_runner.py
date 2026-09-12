from __future__ import annotations

from pathlib import Path

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.core.models import Case, SolverResult
from envsolve_harness.progress_state import (
    DeploymentCondition,
    ExecutionEvidence,
    ProjectProgressState,
)
from envsolve_harness.runners.sequential_installer import (
    SequentialInstallerRunner,
    bind_default_target_python,
    verified_conditions,
)
from envsolve_harness.runners.progress_agent import ProgressAgentRunner
from envsolve_harness.storage.artifacts import RunArtifacts


CASE = Case("case", "owner/repo", "a" * 40)


def condition(identifier: str, python: str) -> DeploymentCondition:
    return DeploymentCondition(
        condition_id=identifier,
        operating_system="linux",
        architecture="arm64",
        python_version=python,
        image="envbench:test",
    )


def passing(python: str) -> ExecutionEvidence:
    return ExecutionEvidence(
        status="pass",
        source="clean-replay",
        bootstrap_exit_code=0,
        public_goal_passed=True,
        observed_python=python,
    )


def state() -> ProjectProgressState:
    initial = ProjectProgressState.start(
        case_id=CASE.case_id,
        repository=CASE.repository,
        revision=CASE.revision,
        program="python3.11 -m venv .venv",
        condition=condition("d0", "3.11"),
        evidence=passing("3.11"),
    )
    return initial.record(
        condition=condition("d1", "3.10"),
        program="python3.10 -m venv .venv",
        evidence=passing("3.10"),
    )


def runner(tmp_path: Path, arm: str) -> SequentialInstallerRunner:
    state_path = tmp_path / "state.json"
    write_json(state_path, state().to_dict())
    return SequentialInstallerRunner(
        installer_arm=arm,  # type: ignore[arg-type]
        state_path=state_path,
        target_condition=condition("d2", "3.11"),
        update_state=True,
        state_output_root=tmp_path / "states",
        ssh_target="user@spark",
        remote_workspace_root="/srv/envsolve",
        docker_executable="docker",
        codex_executable=tmp_path / "codex",
        harness_root=tmp_path,
        source_cache_root=tmp_path / "cache",
        image="envbench:test",
        timeout=120,
        command_timeout=30,
        container_create_timeout=10,
        git_fetch_timeout=20,
        goal_contract=ExecutableGoalContract("goal", "fixture", "true"),
    )


def test_verified_conditions_are_distinct_and_stable() -> None:
    assert [item.condition_id for item in verified_conditions(state())] == ["d0", "d1"]


def test_target_binding_defaults_to_current_condition_but_remains_overridable() -> None:
    program = bind_default_target_python(
        '"python${ENVSOLVE_TARGET_PYTHON}" -m venv .venv',
        "3.10",
    )

    assert program.splitlines()[0] == (
        'export ENVSOLVE_TARGET_PYTHON="${ENVSOLVE_TARGET_PYTHON:-3.10}"'
    )
    updated = bind_default_target_python(program, "3.11")
    assert updated.count("export ENVSOLVE_TARGET_PYTHON=") == 1
    assert "${ENVSOLVE_TARGET_PYTHON:-3.11}" in updated


def test_static_and_adaptive_prompts_share_program_but_only_adaptive_gets_regressions(
    tmp_path: Path,
) -> None:
    preflight = {"status": "fail", "verification": {}}

    static = runner(tmp_path / "static", "static")
    static._progress_state = state()
    static._preflight = preflight
    static_prompt = static._prompt(CASE, static.goal_contract)

    adaptive = runner(tmp_path / "adaptive", "adaptive")
    adaptive._progress_state = state()
    adaptive._preflight = preflight
    adaptive_prompt = adaptive._prompt(CASE, adaptive.goal_contract)

    assert "python3.10 -m venv .venv" in static_prompt
    assert "python3.10 -m venv .venv" in adaptive_prompt
    assert "ENVSOLVE_TARGET_PYTHON" in static_prompt
    assert "ENVSOLVE_TARGET_PYTHON" in adaptive_prompt
    assert "historical_regression_conditions" not in static_prompt
    assert "historical_regression_conditions" in adaptive_prompt
    assert "'condition_id': 'd0'" in adaptive_prompt
    assert "'condition_id': 'd1'" in adaptive_prompt


def test_replay_exposes_the_same_explicit_target_input_to_each_arm(
    tmp_path: Path,
    monkeypatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_replay(
        self,
        case,
        *,
        program,
        root,
        condition=None,
    ):
        del self, case, root
        observed["program"] = program
        observed["condition"] = condition
        return {"status": "pass"}

    monkeypatch.setattr(ProgressAgentRunner, "replay_program", fake_replay)
    subject = runner(tmp_path, "static")
    result = subject.replay_program(
        CASE,
        program="echo deploy",
        root=tmp_path / "replay",
        condition=condition("d2", "3.11"),
    )

    assert observed["program"] == (
        "export ENVSOLVE_TARGET_PYTHON=3.11\necho deploy"
    )
    assert result["installer_input"] == {"ENVSOLVE_TARGET_PYTHON": "3.11"}


def test_adaptive_update_does_not_replace_installer_after_historical_regression(
    tmp_path: Path,
    monkeypatch,
) -> None:
    subject = runner(tmp_path, "adaptive")
    original = state()
    subject._progress_state = original
    subject._preflight = {"status": "fail", "verification": {}}
    artifacts = RunArtifacts.create(tmp_path / "runs", "run", CASE.case_id)
    artifacts.generated_script.write_text(
        "python3.11 -m venv .venv",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        subject,
        "replay_program",
        lambda *args, **kwargs: {
            "status": "fail",
            "target_condition": kwargs["condition"].to_dict(),
            "replay_wall_seconds": 1.0,
        },
    )

    metadata = subject._update_progress_state(
        SolverResult(
            True,
            "envsolve-pro-sequential-adaptive",
            script_path="scripts/generated.sh",
        ),
        artifacts,
    )

    assert metadata["installer_candidate_retained"] is False
    updated = ProjectProgressState.from_dict(
        read_json(Path(metadata["state_output_path"]))
    )
    assert updated.current_program == original.current_program
    assert updated.deployments[-1].evidence.source == "historical-regression"
