from __future__ import annotations

from pathlib import Path

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.boundary_v4 import (
    BoundaryV4MinimalBExecutableGoalVerifier,
    BoundaryV4OpenCandidateProgramValidator,
)
from envsolve_harness.codex import (
    minimal_b_mcp,
    minimal_b_mcp_boundary_v4_qualified,
    one_shot_mcp,
    one_shot_mcp_boundary_v4_qualified,
)
from envsolve_harness.core.models import Case, RunSpec
from envsolve_harness.runners.certification_repair_boundary_v4 import (
    CONTROL_METHOD,
    MINIMAL_B_METHOD,
    ONE_SHOT_METHOD,
    BoundaryV4QualifiedCodexCliRunner,
    BoundaryV4QualifiedMinimalBRunner,
    BoundaryV4QualifiedOneShotRunner,
)


def _runner(runner_type: type, root: Path):
    return runner_type(
        codex_executable=root / "codex",
        harness_root=root,
        source_cache_root=root / "cache",
        image="sha256:fixture",
        timeout=100,
        command_timeout=20,
        container_create_timeout=10,
        git_fetch_timeout=10,
        goal_contract=ExecutableGoalContract(
            "goal-v4",
            "Fixture goal",
            "true",
        ),
    )


def test_boundary_v4_runner_names_methods_and_prompt_are_versioned() -> None:
    bindings = (
        (BoundaryV4QualifiedCodexCliRunner, CONTROL_METHOD),
        (BoundaryV4QualifiedOneShotRunner, ONE_SHOT_METHOD),
        (BoundaryV4QualifiedMinimalBRunner, MINIMAL_B_METHOD),
    )
    case = Case("fixture", "org/repo", "a" * 40)

    assert len({runner.runner_name for runner, _ in bindings}) == 3
    assert len({method for _, method in bindings}) == 3
    for runner_type, method in bindings:
        assert "boundary-v4" in runner_type.runner_name
        assert "boundary-v4" in method
        runner = runner_type.__new__(runner_type)
        prompt = runner._prompt(case, None)
        assert prompt.count(BoundaryV4OpenCandidateProgramValidator.prompt_contract) == 1
        assert "create or rewrite build" in prompt


def test_boundary_v4_methods_select_only_their_public_goal(tmp_path: Path) -> None:
    fixtures = (
        (BoundaryV4QualifiedCodexCliRunner, CONTROL_METHOD),
        (BoundaryV4QualifiedOneShotRunner, ONE_SHOT_METHOD),
        (BoundaryV4QualifiedMinimalBRunner, MINIMAL_B_METHOD),
    )
    for runner_type, method in fixtures:
        runner = _runner(runner_type, tmp_path)
        selected = runner._goal_contract_for_run(RunSpec("run", method, "gpt-5.5"))
        assert selected is runner.goal_contract


def test_boundary_v4_mcp_entrypoints_install_policy_and_verifier(monkeypatch) -> None:
    installed: list[str] = []
    observed: list[tuple[object, object]] = []
    monkeypatch.setattr(
        minimal_b_mcp_boundary_v4_qualified,
        "install_boundary_v4_local_distribution_audit",
        lambda: installed.append("audit"),
    )
    monkeypatch.setattr(
        one_shot_mcp_boundary_v4_qualified,
        "install_boundary_v4_local_distribution_audit",
        lambda: installed.append("audit"),
    )

    def observe() -> int:
        observed.append(
            (
                minimal_b_mcp.MinimalBExecutableGoalVerifier,
                minimal_b_mcp.OpenCandidateProgramValidator,
            )
        )
        return 0

    monkeypatch.setattr(minimal_b_mcp, "main", observe)
    monkeypatch.setattr(one_shot_mcp, "main", observe)

    assert minimal_b_mcp_boundary_v4_qualified.main() == 0
    assert one_shot_mcp_boundary_v4_qualified.main() == 0
    assert installed == ["audit", "audit"]
    assert observed == [
        (
            BoundaryV4MinimalBExecutableGoalVerifier,
            BoundaryV4OpenCandidateProgramValidator,
        ),
        (
            BoundaryV4MinimalBExecutableGoalVerifier,
            BoundaryV4OpenCandidateProgramValidator,
        ),
    ]


def test_boundary_v4_replay_runners_use_versioned_mcp_modules(
    tmp_path: Path,
) -> None:
    trace = tmp_path / "generation" / "commands.jsonl"
    trace.parent.mkdir(parents=True)
    case = Case("fixture", "owner/repo", "a" * 40, language="python")
    fixtures = (
        (
            BoundaryV4QualifiedOneShotRunner,
            "envsolve_harness.codex.one_shot_mcp_boundary_v4_qualified",
        ),
        (
            BoundaryV4QualifiedMinimalBRunner,
            "envsolve_harness.codex.minimal_b_mcp_boundary_v4_qualified",
        ),
    )

    for runner_type, module in fixtures:
        runner = _runner(runner_type, tmp_path)
        arguments = runner._mcp_server_args(
            trace_path=trace,
            container_id="container-1",
            case=case,
            image_digest="sha256:fixture",
        )
        assert module in arguments
        assert not any("boundary_v3_qualified" in value for value in arguments)
