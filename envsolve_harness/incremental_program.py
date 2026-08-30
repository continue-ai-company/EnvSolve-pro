from __future__ import annotations

from pathlib import Path
from typing import Any

from envsolve_harness.codex.minimal_b_mcp import canonical_script
from envsolve_harness.core.io import write_jsonl, write_text_atomic


INCREMENTAL_PROGRAM_SCHEMA = "envsolve-pro-incremental-program-v1"


class IncrementalProgram:
    """Build one replayable program from successful model-selected operations."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.steps_path = root / "steps.jsonl"
        self.program_path = root / "current-program.sh"
        self.steps: list[dict[str, Any]] = []

    @property
    def program(self) -> str:
        return "\n\n".join(str(step["command"]) for step in self.steps)

    def append_successful(self, command: str, result: dict[str, Any]) -> dict[str, Any]:
        command = canonical_script(command)
        if not command:
            raise ValueError("incremental program step cannot be empty")
        if (
            result.get("exit_code") != 0
            or result.get("timed_out") is True
            or result.get("infrastructure_error") is not None
        ):
            raise ValueError("only a successful executed command can become a program step")
        step = {
            "schema": INCREMENTAL_PROGRAM_SCHEMA,
            "step": len(self.steps) + 1,
            "command": command,
            "construction_exit_code": 0,
        }
        self.steps.append(step)
        self._persist()
        return step

    def revise(self, step_index: int, replacement_command: str) -> dict[str, Any]:
        if isinstance(step_index, bool) or not isinstance(step_index, int):
            raise ValueError("step index must be an integer")
        if step_index < 1 or step_index > len(self.steps):
            raise ValueError(
                f"step index must be between 1 and {len(self.steps)}"
            )

        previous_command = str(self.steps[step_index - 1]["command"])
        replacement = canonical_script(replacement_command)
        operation = "replace" if replacement else "delete"
        if replacement:
            self.steps[step_index - 1] = {
                "schema": INCREMENTAL_PROGRAM_SCHEMA,
                "step": step_index,
                "command": replacement,
                "source": "model-plan-revision",
            }
        else:
            del self.steps[step_index - 1]
        for index, step in enumerate(self.steps, start=1):
            step["step"] = index
        self._persist()
        return {
            "schema": INCREMENTAL_PROGRAM_SCHEMA,
            "operation": operation,
            "step_index": step_index,
            "previous_command": previous_command,
            "replacement_command": replacement,
        }

    def indexed_steps(self) -> list[dict[str, Any]]:
        return [
            {"step": index, "command": str(step["command"])}
            for index, step in enumerate(self.steps, start=1)
        ]

    def _persist(self) -> None:
        write_jsonl(self.steps_path, self.steps)
        write_text_atomic(
            self.program_path,
            self.program + ("\n" if self.program else ""),
        )

    def metadata(self) -> dict[str, Any]:
        return {
            **self.state(),
            "steps_path": str(self.steps_path),
            "program_path": str(self.program_path),
        }

    def state(self) -> dict[str, Any]:
        return {
            "schema": INCREMENTAL_PROGRAM_SCHEMA,
            "step_count": len(self.steps),
            "program_nonblank_line_count": sum(
                bool(line.strip()) for line in self.program.splitlines()
            ),
            "model_selected_steps": True,
            "failed_commands_recorded": False,
            "stores_container_checkpoint": False,
        }
