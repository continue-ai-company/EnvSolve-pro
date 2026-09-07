from __future__ import annotations

from pathlib import Path

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.boundary_v6 import (
    BoundaryV6MinimalBExecutableGoalVerifier,
    BoundaryV6OpenCandidateProgramValidator,
)
from envsolve_harness.codex import (
    minimal_b_mcp,
    minimal_b_mcp_boundary_v6_qualified,
)
from envsolve_harness.core.models import Case
from envsolve_harness.runners.certification_repair_boundary_v6 import (
    BoundaryV6QualifiedCodexCliRunner,
    BoundaryV6QualifiedMinimalBRunner,
)
from envsolve_harness.runners.certification_repair_boundary_v5 import (
    BoundaryV5QualifiedCodexCliRunner,
)
from envsolve_harness.runners.remote_boundary_v6 import (
    RemoteBoundaryV6QualifiedCodexCliRunner,
    RemoteBoundaryV6QualifiedMinimalBRunner,
)


def _runner(runner_type: type, root: Path):
    kwargs = {
        "codex_executable": root / "codex",
        "harness_root": root,
        "source_cache_root": root / "cache",
        "image": "sha256:fixture",
        "timeout": 100,
        "command_timeout": 20,
        "container_create_timeout": 10,
        "git_fetch_timeout": 10,
        "goal_contract": ExecutableGoalContract("goal-v6", "Fixture", "true"),
    }
    if issubclass(runner_type, RemoteBoundaryV6QualifiedCodexCliRunner):
        kwargs.update(
            {
                "ssh_target": "user@spark",
                "remote_workspace_root": "/srv/envsolve",
            }
        )
    return runner_type(**kwargs)


def test_a_and_b_share_the_exact_v6_candidate_contract(tmp_path: Path) -> None:
    case = Case("fixture", "org/repo", "a" * 40)
    runner_types = (
        BoundaryV6QualifiedCodexCliRunner,
        BoundaryV6QualifiedMinimalBRunner,
        RemoteBoundaryV6QualifiedCodexCliRunner,
        RemoteBoundaryV6QualifiedMinimalBRunner,
    )

    prompts = [_runner(item, tmp_path)._prompt(case, None) for item in runner_types]

    for prompt in prompts:
        contract = BoundaryV6OpenCandidateProgramValidator.prompt_contract
        assert prompt.count(contract) == 1
        assert "operation space is open" in prompt
        assert "type-only `.pyi` providers" in prompt
        assert "must not edit repository source or configuration" not in prompt

    for runner_type in (
        BoundaryV6QualifiedMinimalBRunner,
        RemoteBoundaryV6QualifiedMinimalBRunner,
    ):
        runner = _runner(runner_type, tmp_path)
        prompt = runner._prompt(case, runner.goal_contract)
        assert "shared v6 boundary leaves deployment operations open" in prompt
        assert "rejects candidate-generated compatibility packages" not in prompt


def test_all_v6_finalizers_use_the_v6_artifact_policy(tmp_path: Path) -> None:
    script = (
        "mkdir -p src/pkg\n"
        "printf 'VALUE = 1\\n' > src/pkg/generated.py\n"
    )
    runner_types = (
        BoundaryV6QualifiedCodexCliRunner,
        BoundaryV6QualifiedMinimalBRunner,
        RemoteBoundaryV6QualifiedCodexCliRunner,
        RemoteBoundaryV6QualifiedMinimalBRunner,
    )

    for runner_type in runner_types:
        validation = _runner(runner_type, tmp_path)._validate_bootstrap(script)
        assert validation.accepted
        assert validation.policy_id == "open-candidate-program-v6.1"

    v5 = BoundaryV5QualifiedCodexCliRunner.__new__(
        BoundaryV5QualifiedCodexCliRunner
    )
    assert not v5._validate_bootstrap(script).accepted


def test_v6_minimal_b_entrypoint_installs_v6_validator_and_verifier(
    monkeypatch,
) -> None:
    observed: list[tuple[object, object]] = []
    original_verifier = minimal_b_mcp.MinimalBExecutableGoalVerifier
    original_validator = minimal_b_mcp.OpenCandidateProgramValidator
    monkeypatch.setattr(
        minimal_b_mcp_boundary_v6_qualified,
        "install_boundary_v6_local_distribution_audit",
        lambda: None,
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

    try:
        assert minimal_b_mcp_boundary_v6_qualified.main() == 0
    finally:
        minimal_b_mcp.MinimalBExecutableGoalVerifier = original_verifier
        minimal_b_mcp.OpenCandidateProgramValidator = original_validator
    assert observed == [
        (
            BoundaryV6MinimalBExecutableGoalVerifier,
            BoundaryV6OpenCandidateProgramValidator,
        )
    ]


def test_v6_local_and_remote_b_route_to_versioned_replay_modules(
    tmp_path: Path,
) -> None:
    case = Case("fixture", "org/repo", "a" * 40)
    trace = tmp_path / "trace.jsonl"
    fixtures = (
        (
            _runner(BoundaryV6QualifiedMinimalBRunner, tmp_path),
            "envsolve_harness.codex.minimal_b_mcp_boundary_v6_qualified",
        ),
        (
            _runner(RemoteBoundaryV6QualifiedMinimalBRunner, tmp_path),
            "envsolve_harness.codex.remote_minimal_b_mcp_boundary_v6",
        ),
    )

    for runner, module in fixtures:
        arguments = runner._mcp_server_args(
            trace_path=trace,
            container_id="container",
            case=case,
            image_digest="sha256:fixture",
        )
        assert module in arguments
        assert not any("boundary_v5_qualified" in value for value in arguments)
