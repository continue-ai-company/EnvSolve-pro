from __future__ import annotations

from envsolve_harness import boundary_v2
from envsolve_harness.codex import (
    minimal_b_mcp,
    minimal_b_mcp_boundary_v2_qualified,
    one_shot_mcp,
    one_shot_mcp_boundary_v2_qualified,
)
from envsolve_harness.runners.certification_repair_boundary_v2 import (
    CONTROL_METHOD,
    MINIMAL_B_METHOD,
    ONE_SHOT_METHOD,
    BoundaryV2QualifiedCodexCliRunner,
    BoundaryV2QualifiedMinimalBRunner,
    BoundaryV2QualifiedOneShotRunner,
)


def test_boundary_v2_runner_names_and_methods_are_distinct_from_v1() -> None:
    bindings = (
        (BoundaryV2QualifiedCodexCliRunner, CONTROL_METHOD),
        (BoundaryV2QualifiedOneShotRunner, ONE_SHOT_METHOD),
        (BoundaryV2QualifiedMinimalBRunner, MINIMAL_B_METHOD),
    )

    assert len({runner.runner_name for runner, _ in bindings}) == 3
    assert len({method for _, method in bindings}) == 3
    assert all("boundary-v2" in runner.runner_name for runner, _ in bindings)
    assert all("boundary-v2" in method for _, method in bindings)


def test_boundary_v2_mcp_entrypoints_install_versioned_audit(monkeypatch) -> None:
    installed: list[str] = []
    monkeypatch.setattr(
        boundary_v2,
        "install_boundary_v2_local_distribution_audit",
        lambda: installed.append("audit"),
    )
    monkeypatch.setattr(
        minimal_b_mcp,
        "MinimalBExecutableGoalVerifier",
        minimal_b_mcp.MinimalBExecutableGoalVerifier,
    )
    monkeypatch.setattr(
        minimal_b_mcp,
        "PersistentContainerShell",
        minimal_b_mcp.PersistentContainerShell,
    )
    monkeypatch.setattr(minimal_b_mcp, "main", lambda: 0)
    monkeypatch.setattr(one_shot_mcp, "main", lambda: 0)

    assert minimal_b_mcp_boundary_v2_qualified.main() == 0
    assert one_shot_mcp_boundary_v2_qualified.main() == 0

    assert installed == ["audit", "audit"]
