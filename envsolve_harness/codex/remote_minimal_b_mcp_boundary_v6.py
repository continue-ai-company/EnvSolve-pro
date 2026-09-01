#!/usr/bin/env python3
from __future__ import annotations

from envsolve_harness.boundary_v6 import (
    BoundaryV6OfficialAlignedExecutableGoalVerifier,
    BoundaryV6OpenCandidateProgramValidator,
)
from envsolve_harness.codex import remote_minimal_b_mcp_boundary_v5 as implementation


def main() -> int:
    implementation.BoundaryV5OfficialAlignedExecutableGoalVerifier = (
        BoundaryV6OfficialAlignedExecutableGoalVerifier
    )
    implementation.BoundaryV5OpenCandidateProgramValidator = (
        BoundaryV6OpenCandidateProgramValidator
    )
    return implementation.main()


if __name__ == "__main__":
    raise SystemExit(main())
