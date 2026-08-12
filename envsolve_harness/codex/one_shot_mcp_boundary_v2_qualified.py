#!/usr/bin/env python3
from __future__ import annotations

from envsolve_harness import boundary_v2
from envsolve_harness.codex import minimal_b_mcp, one_shot_mcp
from envsolve_harness.codex.container_mcp_qualified import (
    ProcessTreeSafePersistentContainerShell,
)


def main() -> int:
    boundary_v2.install_boundary_v2_local_distribution_audit()
    minimal_b_mcp.MinimalBExecutableGoalVerifier = (
        boundary_v2.BoundaryV2MinimalBExecutableGoalVerifier
    )
    minimal_b_mcp.PersistentContainerShell = ProcessTreeSafePersistentContainerShell
    return one_shot_mcp.main()


if __name__ == "__main__":
    raise SystemExit(main())
