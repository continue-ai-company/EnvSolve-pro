#!/usr/bin/env python3
from __future__ import annotations

from envsolve_harness.boundary_v3 import (
    BoundaryV3MinimalBExecutableGoalVerifier,
    BoundaryV3OpenCandidateProgramValidator,
    install_boundary_v3_local_distribution_audit,
)
from envsolve_harness.codex import minimal_b_mcp, one_shot_mcp
from envsolve_harness.codex.container_mcp_qualified import (
    ProcessTreeSafePersistentContainerShell,
)


def main() -> int:
    install_boundary_v3_local_distribution_audit()
    minimal_b_mcp.MinimalBExecutableGoalVerifier = (
        BoundaryV3MinimalBExecutableGoalVerifier
    )
    minimal_b_mcp.OpenCandidateProgramValidator = (
        BoundaryV3OpenCandidateProgramValidator
    )
    minimal_b_mcp.PersistentContainerShell = ProcessTreeSafePersistentContainerShell
    return one_shot_mcp.main()


if __name__ == "__main__":
    raise SystemExit(main())
