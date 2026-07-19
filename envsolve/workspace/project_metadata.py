from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re
from typing import Iterable, Mapping, Sequence


_EXTRA_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_TEST_EXTRA_ALIASES = frozenset({"test", "tests", "testing"})
_TEST_PATH_COMPONENTS = frozenset({"test", "tests"})


@dataclass(frozen=True)
class MissingImportObligation:
    module: str
    file: str

    @property
    def source_role(self) -> str:
        parts = PurePosixPath(self.file).parts
        return "test" if any(part.lower() in _TEST_PATH_COMPONENTS for part in parts) else "runtime"


@dataclass(frozen=True)
class ProjectExtra:
    name: str
    requirements: tuple[str, ...]
    metadata_sha256: str
    selected_by_test_tool: bool

    def is_valid(self) -> bool:
        return (
            bool(_EXTRA_NAME.fullmatch(self.name))
            and bool(self.requirements)
            and len(self.metadata_sha256) == 64
        )


@dataclass(frozen=True)
class ProjectExtraRepair:
    extra: ProjectExtra
    obligations: tuple[MissingImportObligation, ...]

    def install_command(self) -> str:
        if not self.extra.is_valid():
            raise ValueError("invalid project extra evidence")
        return f'python -m pip install --no-build-isolation -e ".[{self.extra.name}]"'


class ProjectExtraPolicy:
    def extras_from_metadata(
        self,
        optional_dependencies: Mapping[str, Sequence[str]],
        metadata_sha256: str,
        test_tool_extras: Iterable[str],
    ) -> tuple[ProjectExtra, ...]:
        selected = frozenset(test_tool_extras)
        extras = []
        for name, requirements in optional_dependencies.items():
            extra = ProjectExtra(
                name=str(name),
                requirements=tuple(str(item) for item in requirements),
                metadata_sha256=metadata_sha256,
                selected_by_test_tool=str(name) in selected,
            )
            if extra.is_valid():
                extras.append(extra)
        return tuple(sorted(extras, key=lambda item: item.name))

    def plan(
        self,
        obligations: Iterable[MissingImportObligation],
        extras: Iterable[ProjectExtra],
    ) -> ProjectExtraRepair | None:
        required = tuple(obligations)
        if not required or any(item.source_role != "test" for item in required):
            return None
        candidates = tuple(
            item
            for item in extras
            if item.name.lower() in _TEST_EXTRA_ALIASES and item.selected_by_test_tool
        )
        if len(candidates) != 1:
            return None
        return ProjectExtraRepair(candidates[0], required)
