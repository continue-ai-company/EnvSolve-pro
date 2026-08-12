#!/usr/bin/env python3
from __future__ import annotations

from envsolve_harness.boundary_v5 import (
    BoundaryV5MinimalBExecutableGoalVerifier,
    BoundaryV5OpenCandidateProgramValidator,
    install_boundary_v5_local_distribution_audit,
)
from envsolve_harness.codex import minimal_b_mcp
from envsolve_harness.codex.container_mcp_qualified import (
    ProcessTreeSafePersistentContainerShell,
)


def main() -> int:
    install_boundary_v5_local_distribution_audit()
    minimal_b_mcp.MinimalBExecutableGoalVerifier = (
        BoundaryV5MinimalBExecutableGoalVerifier
    )
    minimal_b_mcp.OpenCandidateProgramValidator = (
        BoundaryV5OpenCandidateProgramValidator
    )
    minimal_b_mcp.PersistentContainerShell = ProcessTreeSafePersistentContainerShell
    return minimal_b_mcp.main()


if __name__ == "__main__":
    raise SystemExit(main())
