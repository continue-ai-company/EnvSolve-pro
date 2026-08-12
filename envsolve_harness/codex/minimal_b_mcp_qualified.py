#!/usr/bin/env python3
from __future__ import annotations

from envsolve_harness.codex import minimal_b_mcp
from envsolve_harness.codex.container_mcp_qualified import (
    ProcessTreeSafePersistentContainerShell,
)


def main() -> int:
    minimal_b_mcp.PersistentContainerShell = ProcessTreeSafePersistentContainerShell
    return minimal_b_mcp.main()


if __name__ == "__main__":
    raise SystemExit(main())
