from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from envsolve.v0.verification import V0CompletionDecision, completion_from_trajectory
from envsolve_harness.scripts.envbench_trajectory import (
    TrajectoryDistillationResult,
    commands_from_trajectory,
    distill_envbench_commands,
)


@dataclass(frozen=True)
class V0Finalization:
    completion: V0CompletionDecision
    distillation: TrajectoryDistillationResult | None
    error: str | None


def finalize_v0_trajectory(
    records: list[dict[str, Any]], project_directory: str
) -> V0Finalization:
    completion = completion_from_trajectory(records)
    if not completion.passed:
        return V0Finalization(completion, None, completion.reason)
    try:
        commands = commands_from_trajectory(records)
        distilled = distill_envbench_commands(commands, project_directory)
    except (TypeError, ValueError) as exc:
        return V0Finalization(completion, None, f"trajectory distillation failed: {exc}")
    if distilled.unknown_commands:
        return V0Finalization(
            completion,
            distilled,
            f"trajectory contains unsupported commands: {list(distilled.unknown_commands)}",
        )
    if not distilled.kept_commands:
        return V0Finalization(completion, distilled, "trajectory contains no replayable mutation")
    return V0Finalization(completion, distilled, None)

