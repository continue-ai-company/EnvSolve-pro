#!/usr/bin/env python3
from __future__ import annotations

from envsolve_harness.boundary_v4 import (
    BoundaryV4MinimalBExecutableGoalVerifier,
    BoundaryV4OpenCandidateProgramValidator,
    install_boundary_v4_local_distribution_audit,
)
from envsolve_harness.codex import minimal_b_mcp, one_shot_mcp
from envsolve_harness.codex.container_mcp_qualified import (
    ProcessTreeSafePersistentContainerShell,
)


def main() -> int:
    install_boundary_v4_local_distribution_audit()
    minimal_b_mcp.MinimalBExecutableGoalVerifier = (
        BoundaryV4MinimalBExecutableGoalVerifier
    )
    minimal_b_mcp.OpenCandidateProgramValidator = (
        BoundaryV4OpenCandidateProgramValidator
    )
    minimal_b_mcp.PersistentContainerShell = ProcessTreeSafePersistentContainerShell
    return one_shot_mcp.main()


if __name__ == "__main__":
    raise SystemExit(main())
