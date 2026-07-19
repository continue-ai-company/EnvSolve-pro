from __future__ import annotations

from dataclasses import dataclass
import ast
import re
import shlex
from pathlib import PurePosixPath
from typing import Iterable


_MULTIPLE_TOP_LEVEL = re.compile(
    r"Multiple top-level packages discovered in a flat-layout:\s*(\[[^\n]+\])"
)


@dataclass(frozen=True)
class ArtifactOwnership:
    path: str
    producer: str
    producer_sha256: str
    content_sha256: str
    created_before_bootstrap: bool
    repository_tracked: bool
    is_symlink: bool = False

    def is_relocatable(self) -> bool:
        candidate = PurePosixPath(self.path)
        return (
            bool(self.producer)
            and len(self.producer_sha256) == 64
            and len(self.content_sha256) == 64
            and self.created_before_bootstrap
            and not self.repository_tracked
            and not self.is_symlink
            and not candidate.is_absolute()
            and len(candidate.parts) == 1
            and candidate.name not in {"", ".", ".."}
            and bool(re.fullmatch(r"[A-Za-z0-9._-]+", candidate.name))
        )


@dataclass(frozen=True)
class WorkspaceArtifactConflict:
    discovered_paths: tuple[str, ...]
    owned_paths: tuple[ArtifactOwnership, ...]


@dataclass(frozen=True)
class WorkspaceArtifactRepair:
    conflict: WorkspaceArtifactConflict

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.conflict.owned_paths)

    def render_shell(self, install_command: str) -> str:
        if not install_command.strip() or "\n" in install_command:
            raise ValueError("install command must be one non-empty shell line")
        if not self.paths:
            raise ValueError("Artifact repair requires at least one owned path")
        quoted_paths = tuple(shlex.quote(path) for path in self.paths)
        lines = [
            'envsolve_artifact_tmp="$(mktemp -d)"',
            "envsolve_restore_artifacts() {",
            "  envsolve_artifact_rc=$?",
            "  trap - EXIT",
        ]
        lines.extend(
            f'  mv -- "$envsolve_artifact_tmp/{path}" {quoted}'
            for path, quoted in zip(self.paths, quoted_paths)
        )
        lines.extend(
            [
                '  rmdir -- "$envsolve_artifact_tmp"',
                '  return "$envsolve_artifact_rc"',
                "}",
                "trap envsolve_restore_artifacts EXIT",
            ]
        )
        lines.extend(
            f'mv -- {quoted} "$envsolve_artifact_tmp/{path}"'
            for path, quoted in zip(self.paths, quoted_paths)
        )
        lines.extend([install_command, "envsolve_restore_artifacts"])
        return "\n".join(lines)


class WorkspaceArtifactPolicy:
    def normalize(
        self,
        diagnostic: str,
        ownership: Iterable[ArtifactOwnership],
    ) -> WorkspaceArtifactConflict | None:
        match = _MULTIPLE_TOP_LEVEL.search(diagnostic)
        if match is None:
            return None
        try:
            parsed = ast.literal_eval(match.group(1))
        except (SyntaxError, ValueError):
            return None
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            return None
        discovered = tuple(sorted(set(parsed)))
        records = {
            record.path: record
            for record in ownership
            if record.path in discovered and record.is_relocatable()
        }
        if not records:
            return None
        return WorkspaceArtifactConflict(
            discovered_paths=discovered,
            owned_paths=tuple(records[path] for path in sorted(records)),
        )

    def plan(self, conflict: WorkspaceArtifactConflict) -> WorkspaceArtifactRepair:
        if not conflict.owned_paths:
            raise ValueError("workspace artifact conflict has no verified owned paths")
        return WorkspaceArtifactRepair(conflict)
