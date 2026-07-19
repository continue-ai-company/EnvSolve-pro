from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


LEVELS = tuple(f"V{index}" for index in range(7))


@dataclass(frozen=True)
class VerificationLevel:
    level: str
    passed: bool | None
    verifier: str
    evidence: str
    applicable: bool = True

    def __post_init__(self) -> None:
        if self.level not in LEVELS:
            raise ValueError(f"unknown verifier level: {self.level}")


@dataclass(frozen=True)
class HierarchicalReport:
    levels: tuple[VerificationLevel, ...]

    def _mapping(self) -> Mapping[str, VerificationLevel]:
        return {item.level: item for item in self.levels}

    @property
    def official_pass(self) -> bool:
        values = self._mapping()
        return values.get("V0") is not None and values["V0"].passed is True and values.get("V2") is not None and values["V2"].passed is True

    @property
    def robust_pass(self) -> bool:
        values = self._mapping()
        return all(values.get(level) is not None and values[level].passed is True for level in ("V0", "V1", "V2", "V3", "V4", "V6"))

    @property
    def native_pass(self) -> bool | None:
        values = self._mapping()
        native = values.get("V5")
        if native is None or not native.applicable:
            return None
        return self.robust_pass and native.passed is True

    def pass_curve(self) -> dict[str, bool | None]:
        values = self._mapping()
        return {level: values[level].passed if level in values else None for level in LEVELS}


def build_report(levels: tuple[VerificationLevel, ...]) -> HierarchicalReport:
    identifiers = [item.level for item in levels]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate verifier level")
    return HierarchicalReport(tuple(sorted(levels, key=lambda item: int(item.level[1:]))))

