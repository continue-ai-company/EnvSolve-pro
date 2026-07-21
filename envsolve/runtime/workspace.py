from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Literal


@dataclass(frozen=True)
class WorkspacePrecondition:
    """Non-outcome workspace state owned by an execution adapter."""

    path: str
    kind: Literal["directory"] = "directory"
    producer: str = "benchmark-adapter"

    def __post_init__(self) -> None:
        candidate = PurePosixPath(self.path)
        if (
            candidate.is_absolute()
            or not candidate.parts
            or any(part in {"", ".", ".."} for part in candidate.parts)
        ):
            raise ValueError("Workspace precondition path must stay below the project root")
        if self.kind != "directory":
            raise ValueError("Unsupported workspace precondition kind")
        if not self.producer.strip():
            raise ValueError("Workspace precondition producer cannot be empty")

    def materialize(self, root: Path) -> None:
        target = root.joinpath(*PurePosixPath(self.path).parts)
        target.mkdir(parents=True, exist_ok=True)

    def satisfied_by(self, root: Path) -> bool:
        target = root.joinpath(*PurePosixPath(self.path).parts)
        return target.is_dir() and not target.is_symlink()

    def to_dict(self) -> dict[str, str]:
        return asdict(self)
