from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

from experiments import run_schedule


RunScheduledProcess = Callable[..., dict[str, Any]]


def install_runner_entrypoints(
    entrypoints: Mapping[str, str],
) -> None:
    """Route experimental runners without modifying the frozen coordinator."""

    original: RunScheduledProcess = run_schedule.run_scheduled_process
    root = Path(run_schedule.ROOT)

    def dispatched(
        command: list[object],
        *,
        cwd: Path,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        rewritten = list(command)
        try:
            runner_index = rewritten.index("--runner") + 1
        except (ValueError, IndexError):
            return original(
                rewritten,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
            )
        entrypoint = entrypoints.get(str(rewritten[runner_index]))
        if entrypoint is not None:
            rewritten[1] = str(root / entrypoint)
        return original(
            rewritten,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )

    run_schedule.run_scheduled_process = dispatched
