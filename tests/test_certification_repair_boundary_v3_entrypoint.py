from __future__ import annotations

from envsolve_harness.boundary_v3 import (
    BoundaryV3MinimalBExecutableGoalVerifier,
    BoundaryV3OpenCandidateProgramValidator,
)
from envsolve_harness.codex import (
    minimal_b_mcp,
    minimal_b_mcp_boundary_v3_qualified,
    one_shot_mcp,
    one_shot_mcp_boundary_v3_qualified,
)
from envsolve_harness.core.models import Case
from envsolve_harness.core.models import RunSpec, SolverResult
from envsolve_harness.runners.certification_repair_boundary_v3 import (
    CONTROL_METHOD,
    MINIMAL_B_METHOD,
    ONE_SHOT_METHOD,
    BoundaryV3QualifiedCodexCliRunner,
    BoundaryV3QualifiedMinimalBRunner,
    BoundaryV3QualifiedOneShotRunner,
)
from envsolve_harness.runners.certification_repair_boundary_v2 import (
    BoundaryV2QualifiedCodexCliRunner,
)
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.core.io import write_json


def test_boundary_v3_runner_names_methods_and_prompt_are_versioned() -> None:
    bindings = (
        (BoundaryV3QualifiedCodexCliRunner, CONTROL_METHOD),
        (BoundaryV3QualifiedOneShotRunner, ONE_SHOT_METHOD),
        (BoundaryV3QualifiedMinimalBRunner, MINIMAL_B_METHOD),
    )
    case = Case("fixture", "org/repo", "a" * 40)

    assert len({runner.runner_name for runner, _ in bindings}) == 3
    assert len({method for _, method in bindings}) == 3
    for runner_type, method in bindings:
        assert "boundary-v3" in runner_type.runner_name
        assert "boundary-v3" in method
        runner = runner_type.__new__(runner_type)
        prompt = runner._prompt(case, None)
        assert "even temporarily" in prompt
        assert "temporary `setup.py` may be used" not in prompt


def test_boundary_v3_mcp_entrypoints_install_policy_and_verifier(monkeypatch) -> None:
    installed: list[str] = []
    observed: list[tuple[object, object]] = []
    monkeypatch.setattr(
        minimal_b_mcp_boundary_v3_qualified,
        "install_boundary_v3_local_distribution_audit",
        lambda: installed.append("audit"),
    )
    monkeypatch.setattr(
        one_shot_mcp_boundary_v3_qualified,
        "install_boundary_v3_local_distribution_audit",
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

    assert minimal_b_mcp_boundary_v3_qualified.main() == 0
    assert one_shot_mcp_boundary_v3_qualified.main() == 0
    assert installed == ["audit", "audit"]
    assert observed == [
        (
            BoundaryV3MinimalBExecutableGoalVerifier,
            BoundaryV3OpenCandidateProgramValidator,
        ),
        (
            BoundaryV3MinimalBExecutableGoalVerifier,
            BoundaryV3OpenCandidateProgramValidator,
        ),
    ]


def test_boundary_v3_recovers_from_construction_workspace_rejection(
    monkeypatch,
    tmp_path,
) -> None:
    artifacts = RunArtifacts.create(tmp_path, "run", "case")
    output = artifacts.generation_dir / "codex-control" / "final-output.json"
    write_json(
        output,
        {
            "bootstrap_script": "python -m venv .venv\n. .venv/bin/activate",
            "summary": "fixture",
        },
    )
    initial = SolverResult(
        False,
        CONTROL_METHOD,
        trajectory_path="generation/trajectory.jsonl",
        error="RuntimeError: Codex CLI repository integrity failed: fixture",
        metadata={
            "repository_integrity": {"valid": False, "violations": ["fixture"]},
            "checked_out_revision": "a" * 40,
        },
    )
    monkeypatch.setattr(
        BoundaryV2QualifiedCodexCliRunner,
        "run",
        lambda *_args, **_kwargs: initial,
    )
    monkeypatch.setattr(
        BoundaryV3QualifiedCodexCliRunner,
        "_nonfeedback_submission_qualification",
        lambda *_args, **_kwargs: {
            "policy": "submitted-state-plus-content-provenance-v7",
            "valid": True,
            "violations": [],
        },
    )
    monkeypatch.setattr(
        BoundaryV3QualifiedCodexCliRunner,
        "_finish_boundary_v3_recovery",
        lambda _self, _artifacts, result, _note: result,
    )
    runner = BoundaryV3QualifiedCodexCliRunner.__new__(
        BoundaryV3QualifiedCodexCliRunner
    )

    result = runner.run(
        Case("case", "org/repo", "a" * 40),
        artifacts,
        RunSpec(CONTROL_METHOD, "gpt-5.5", 1),
    )

    assert result.generation_completed
    assert result.metadata["construction_workspace_integrity"]["valid"] is False
    assert result.metadata["repository_integrity"]["valid"] is True
    assert artifacts.generated_script.is_file()


def test_boundary_v3_qualifies_submission_after_construction_workspace_pass(
    monkeypatch,
    tmp_path,
) -> None:
    artifacts = RunArtifacts.create(tmp_path, "run", "case")
    output = artifacts.generation_dir / "codex-control" / "final-output.json"
    write_json(
        output,
        {
            "bootstrap_script": "python -m venv .venv\n. .venv/bin/activate",
            "summary": "fixture",
        },
    )
    initial = SolverResult(
        True,
        CONTROL_METHOD,
        script_path="generated/bootstrap.sh",
        trajectory_path="generation/trajectory.jsonl",
        metadata={
            "repository_integrity": {"valid": True, "policy": "boundary-v2"},
            "checked_out_revision": "a" * 40,
        },
    )
    monkeypatch.setattr(
        BoundaryV2QualifiedCodexCliRunner,
        "run",
        lambda *_args, **_kwargs: initial,
    )
    qualifications: list[str] = []

    def qualify(_self, script, *_args, **_kwargs):
        qualifications.append(script)
        return {
            "policy": "submitted-state-plus-content-provenance-v7",
            "valid": True,
            "violations": [],
        }

    monkeypatch.setattr(
        BoundaryV3QualifiedCodexCliRunner,
        "_nonfeedback_submission_qualification",
        qualify,
    )
    monkeypatch.setattr(
        BoundaryV3QualifiedCodexCliRunner,
        "_finish_boundary_v3_recovery",
        lambda _self, _artifacts, result, _note: result,
    )
    runner = BoundaryV3QualifiedCodexCliRunner.__new__(
        BoundaryV3QualifiedCodexCliRunner
    )

    result = runner.run(
        Case("case", "org/repo", "a" * 40),
        artifacts,
        RunSpec(CONTROL_METHOD, "gpt-5.5", 1),
    )

    assert result.generation_completed
    assert qualifications == ["python -m venv .venv\n. .venv/bin/activate"]
    assert result.metadata["construction_workspace_integrity"]["valid"] is True
    assert result.metadata["repository_integrity"]["policy"] == (
        "submitted-state-plus-content-provenance-v7"
    )
