from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version


CONTEXT_SCHEMA_VERSION = "1.0.0"
SYSTEM_MANAGER_PRIORITY = ("apt-get", "apk", "dnf", "yum", "brew")
CONTEXT_EVIDENCE_KINDS = {
    "context-tool-observation",
    "context-runtime-root",
    "context-runtime-inventory",
    "context-system-manager-observation",
    "context-capability-package-candidate",
    "context-module-distribution-candidate",
}
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.+-]+$")
SAFE_PACKAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+._:@/-]*$")
SAFE_MODULE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$"
)


class ContextProbeKind(str, Enum):
    TOOL_PRESENCE = "tool_presence"
    RUNTIME_ROOT = "runtime_root"
    RUNTIME_INVENTORY = "runtime_inventory"
    SYSTEM_MANAGER_PRESENCE = "system_manager_presence"


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def validate_name(value: Any, label: str) -> str:
    name = str(value).strip().lower()
    if not SAFE_NAME.fullmatch(name):
        raise ValueError(f"Invalid {label}: {value!r}")
    return name


def validate_module(value: Any) -> str:
    module = str(value).strip().lower()
    if not SAFE_MODULE.fullmatch(module):
        raise ValueError(f"Invalid module name: {value!r}")
    return module


def validate_path(value: Any, present: bool) -> str | None:
    if not present:
        if value not in {None, ""}:
            raise ValueError("Absent tool observation cannot include a path")
        return None
    path = str(value).strip()
    if not path.startswith("/") or "\n" in path or "\r" in path:
        raise ValueError(f"Observed tool path must be absolute: {value!r}")
    return path


def validate_presence(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError("Context presence must be boolean")
    return value


def normalize_versions(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        raise ValueError("Runtime inventory versions must be a list")
    normalized: set[str] = set()
    for value in values:
        try:
            normalized.add(str(Version(str(value))))
        except InvalidVersion as exc:
            raise ValueError(f"Invalid runtime inventory version: {value!r}") from exc
    return tuple(sorted(normalized, key=Version))


def normalize_packages(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list) or not values:
        raise ValueError("System package candidates must be a non-empty list")
    packages = tuple(sorted({str(value).strip() for value in values}))
    if not all(SAFE_PACKAGE.fullmatch(value) for value in packages):
        raise ValueError(f"Invalid system package candidates: {values!r}")
    return packages


def normalize_distributions(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list) or not values:
        raise ValueError("Distribution candidates must be a non-empty list")
    normalized: set[str] = set()
    for value in values:
        try:
            normalized.add(str(Requirement(str(value))))
        except InvalidRequirement as exc:
            raise ValueError(f"Invalid distribution candidate: {value!r}") from exc
    return tuple(sorted(normalized))


@dataclass(frozen=True)
class ParsedContextEvidence:
    evidence_id: str
    kind: str
    confidence: float
    value: dict[str, Any]
    event_sequence: int


def parse_context_evidence(
    evidence_id: str,
    record: dict[str, Any],
) -> ParsedContextEvidence | None:
    kind = str(record.get("kind", "")).strip().lower()
    if kind not in CONTEXT_EVIDENCE_KINDS:
        return None
    confidence = record.get("confidence")
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        raise ValueError(f"Invalid context confidence: {confidence!r}")
    data = require_mapping(record.get("value"), kind)
    state_metadata = record.get("state_metadata", {})
    event_sequence = state_metadata.get("event_sequence", -1)
    if isinstance(event_sequence, bool) or not isinstance(event_sequence, int):
        raise ValueError(f"Invalid context event sequence: {event_sequence!r}")
    if kind in {"context-tool-observation", "context-system-manager-observation"}:
        label = "tool" if kind == "context-tool-observation" else "manager"
        name = validate_name(data.get(label), label)
        if kind == "context-system-manager-observation" and name not in {
            *SYSTEM_MANAGER_PRIORITY,
        }:
            raise ValueError(f"Unsupported system package manager: {name}")
        present = validate_presence(data.get("present"))
        value = {
            label: name,
            "present": present,
            "path": validate_path(data.get("path"), present),
        }
    elif kind in {"context-runtime-root", "context-runtime-inventory"}:
        manager = validate_name(data.get("manager"), "runtime manager")
        if manager != "pyenv":
            raise ValueError(f"Unsupported runtime manager: {manager}")
        if kind == "context-runtime-root":
            value = {
                "manager": manager,
                "root": validate_path(data.get("root"), True),
            }
        else:
            value = {
                "manager": manager,
                "versions": list(normalize_versions(data.get("versions"))),
            }
    elif kind == "context-capability-package-candidate":
        manager = validate_name(data.get("manager"), "system package manager")
        if manager not in {*SYSTEM_MANAGER_PRIORITY}:
            raise ValueError(f"Unsupported system package manager: {manager}")
        value = {
            "capability": validate_name(data.get("capability"), "capability"),
            "manager": manager,
            "packages": list(normalize_packages(data.get("packages"))),
        }
    else:
        value = {
            "module": validate_module(data.get("module")),
            "distributions": list(
                normalize_distributions(data.get("distributions"))
            ),
        }
    return ParsedContextEvidence(
        evidence_id=evidence_id,
        kind=kind,
        confidence=float(confidence),
        value=value,
        event_sequence=event_sequence,
    )
