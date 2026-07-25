from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any


GOAL_REPORT_SCHEMA = "envsolve-goal-report-v1"


@dataclass(frozen=True)
class ExecutableGoalContract:
    """Public task objective expressed as a trusted executable observation."""

    contract_id: str
    description: str
    program: str
    report_schema: str = GOAL_REPORT_SCHEMA
    protected_environment_prefixes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("contract_id", self.contract_id),
            ("description", self.description),
            ("program", self.program),
            ("report_schema", self.report_schema),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Goal contract {name} cannot be empty")
            if "\0" in value:
                raise ValueError(f"Goal contract {name} cannot contain NUL")
        if not isinstance(self.protected_environment_prefixes, tuple):
            raise ValueError(
                "Goal contract protected environment prefixes must be a tuple"
            )
        for prefix in self.protected_environment_prefixes:
            if (
                not isinstance(prefix, str)
                or not prefix
                or "\0" in prefix
                or not (prefix[0].isalpha() or prefix[0] == "_")
                or any(not (character.isalnum() or character == "_") for character in prefix)
            ):
                raise ValueError(
                    "Goal contract protected environment prefixes must be "
                    "non-empty variable-name prefixes"
                )
        if len(set(self.protected_environment_prefixes)) != len(
            self.protected_environment_prefixes
        ):
            raise ValueError(
                "Goal contract protected environment prefixes must be unique"
            )

    @property
    def sha256(self) -> str:
        payload = json.dumps(
            self.to_dict(include_sha256=False),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self, *, include_sha256: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "contract_id": self.contract_id,
            "description": self.description,
            "program": self.program,
            "report_schema": self.report_schema,
            "protected_environment_prefixes": list(
                self.protected_environment_prefixes
            ),
        }
        if include_sha256:
            value["sha256"] = self.sha256
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ExecutableGoalContract:
        if not isinstance(value, dict):
            raise ValueError("Goal contract must be an object")
        allowed = {
            "contract_id",
            "description",
            "program",
            "report_schema",
            "protected_environment_prefixes",
            "sha256",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(
                f"Goal contract contains unknown fields: {sorted(unknown)}"
            )
        prefixes = value.get("protected_environment_prefixes", [])
        if not isinstance(prefixes, list) or not all(
            isinstance(prefix, str) for prefix in prefixes
        ):
            raise ValueError(
                "Goal contract protected_environment_prefixes must be a string array"
            )
        try:
            contract = cls(
                contract_id=value["contract_id"],
                description=value["description"],
                program=value["program"],
                report_schema=value.get("report_schema", GOAL_REPORT_SCHEMA),
                protected_environment_prefixes=tuple(prefixes),
            )
        except KeyError as exc:
            raise ValueError(f"Goal contract is missing {exc.args[0]!r}") from exc
        expected = value.get("sha256")
        if expected is not None and expected != contract.sha256:
            raise ValueError("Goal contract sha256 does not match its contents")
        return contract
