#!/usr/bin/env python3
from __future__ import annotations

from envsolve_harness.codex import minimal_b_mcp
from envsolve_harness.codex.container_mcp_qualified import (
    ProcessTreeSafePersistentContainerShell,
)
from envsolve_harness.codex.one_shot_mcp import main as one_shot_main


def main() -> int:
    minimal_b_mcp.PersistentContainerShell = ProcessTreeSafePersistentContainerShell
    return one_shot_main()


if __name__ == "__main__":
    raise SystemExit(main())
