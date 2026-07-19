from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from envsolve.solver import ActionSpec, CommandResult, SolverStateSession


class TraceAction(Protocol):
    kind: str

    def to_dict(self) -> dict[str, Any]: ...


class TraceCommandAnalysis(Protocol):
    actions: tuple[TraceAction, ...]
    dropped: bool
    unsupported_reason: str | None


class ShellCommandAnalyzer(Protocol):
    def __call__(
        self,
        command: str,
        project_directory: str | None = None,
    ) -> TraceCommandAnalysis: ...


@dataclass(frozen=True)
class ShellTraceSummary:
    commands: int
    typed_actions: int
    observations: int
    unsupported: int
    failed: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _exit_code(record: dict[str, Any]) -> int:
    value = record.get("exit_code", record.get("returncode"))
    if isinstance(value, bool):
        raise ValueError("Shell trace exit code cannot be boolean")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Shell trace record has invalid exit code: {value!r}") from exc


def ingest_shell_command_trace(
    session: SolverStateSession,
    records: list[dict[str, Any]],
    source: str,
    analyzer: ShellCommandAnalyzer,
    project_directory: str | None = None,
) -> ShellTraceSummary:
    typed = observations = unsupported = failed = commands = 0
    for index, record in enumerate(records, start=1):
        command = str(record.get("command", "")).strip()
        if not command:
            continue
        commands += 1
        exit_code = _exit_code(record)
        analysis = analyzer(command, project_directory)
        typed_actions = [action.to_dict() for action in analysis.actions]
        if typed_actions:
            action_type = (
                typed_actions[0]["kind"]
                if len(typed_actions) == 1
                else "compound_typed_shell"
            )
            typed += 1
        elif analysis.dropped:
            action_type = "observation"
            observations += 1
        else:
            action_type = "unsupported_shell"
            unsupported += 1
        result = CommandResult(
            exit_code=exit_code,
            stdout=str(record.get("stdout", record.get("output", ""))),
            stderr=str(record.get("stderr", "")),
            duration_seconds=record.get("duration_seconds"),
        )
        action_id = session.record_action_result(
            ActionSpec(
                action_id=f"trace-action-{index:04d}",
                action_type=action_type,
                command=command,
                rationale="Recorded solver shell interaction",
                metadata={
                    "trace_source": source,
                    "trace_index": index,
                    "typed_actions": typed_actions,
                    "unsupported_reason": analysis.unsupported_reason,
                },
            ),
            result,
            evidence_id=f"trace-evidence-{index:04d}",
            evidence_source=f"{source}#{index}",
        )
        if exit_code != 0:
            failed += 1
    return ShellTraceSummary(commands, typed, observations, unsupported, failed)
