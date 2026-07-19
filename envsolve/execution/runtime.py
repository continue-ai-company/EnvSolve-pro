from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
import shlex
from typing import Any

from envsolve.repairs import RepairContext
from envsolve.state import EnvironmentState


@dataclass(frozen=True)
class RuntimeExecutionContract:
    manager: str
    source_evidence_id: str
    tool_path: str
    path_prepend: tuple[str, ...]
    required_executable: str

    def __post_init__(self) -> None:
        if self.manager != "pyenv":
            raise ValueError(f"Unsupported runtime execution manager: {self.manager}")
        for value in (*self.path_prepend, self.tool_path, self.required_executable):
            if not value.startswith("/") or "\n" in value or "\r" in value:
                raise ValueError(f"Runtime execution path must be absolute: {value!r}")
        if not self.path_prepend:
            raise ValueError("Runtime execution contract requires a PATH prefix")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["path_prepend"] = list(self.path_prepend)
        return value

    def wrap(self, command: str) -> str:
        if not command.strip():
            raise ValueError("Runtime command cannot be empty")
        prefix = ":".join(self.path_prepend)
        required = shlex.quote(self.required_executable)
        return (
            f"test -x {required} || {{ printf '%s\\n' "
            f"'runtime execution contract unavailable' >&2; exit 127; }}\n"
            f"export PATH={shlex.quote(prefix)}:\"$PATH\"\n"
            f"{command}"
        )


def derive_runtime_execution_contract(
    state: EnvironmentState,
    context: RepairContext,
) -> RuntimeExecutionContract:
    if context.runtime_manager != "pyenv":
        raise ValueError("A pyenv repair context is required")
    if context.runtime_root is None:
        raise ValueError("A probed pyenv root is required")
    candidates: list[tuple[str, str]] = []
    for evidence_id in context.evidence_ids:
        record = state.evidence.get(evidence_id, {})
        value = record.get("value")
        if (
            record.get("kind") == "context-tool-observation"
            and isinstance(value, dict)
            and value.get("tool") == "pyenv"
            and value.get("present") is True
        ):
            candidates.append((evidence_id, str(value.get("path", ""))))
    if len(candidates) != 1:
        raise ValueError(
            f"Expected one selected pyenv tool observation, got {len(candidates)}"
        )
    evidence_id, tool_path_value = candidates[0]
    tool_path = PurePosixPath(tool_path_value)
    if tool_path.name != "pyenv":
        raise ValueError(f"Unexpected pyenv executable: {tool_path_value!r}")
    root = PurePosixPath(context.runtime_root)
    shims = root / "shims"
    return RuntimeExecutionContract(
        manager="pyenv",
        source_evidence_id=evidence_id,
        tool_path=str(tool_path),
        path_prepend=(str(shims),),
        required_executable=str(shims / "python"),
    )
