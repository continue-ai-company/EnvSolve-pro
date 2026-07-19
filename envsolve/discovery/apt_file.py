from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
import re
from typing import Any

from envsolve.context.models import normalize_packages, validate_name


APT_FILE_LINE = re.compile(r"^([^\s]+):\s+(.+)$")
ENVIRONMENT_KEYS = ("path", "architecture", "os")


@dataclass(frozen=True, order=True)
class AptFileCandidate:
    package: str
    path: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderEnvironment:
    path: tuple[str, ...]
    architecture: str
    os_id: str
    codename: str

    def __post_init__(self) -> None:
        if not self.path or not all(item.startswith("/") for item in self.path):
            raise ValueError("Provider PATH requires absolute directories")
        for value in (*self.path, self.architecture, self.os_id, self.codename):
            if not value or "\n" in value or "\r" in value:
                raise ValueError("Provider environment values cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["path"] = list(self.path)
        return value


@dataclass(frozen=True)
class AptFileDiscovery:
    capability: str
    manager: str
    candidates: tuple[AptFileCandidate, ...]
    rejected: tuple[dict[str, str], ...]

    @property
    def packages(self) -> tuple[str, ...]:
        if not self.candidates:
            return ()
        return tuple(normalize_packages([item.package for item in self.candidates]))

    def context_value(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "manager": self.manager,
            "packages": list(self.packages),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.context_value(),
            "candidates": [item.to_dict() for item in self.candidates],
            "rejected": list(self.rejected),
        }


def parse_provider_environment(stdout: str) -> ProviderEnvironment:
    values: dict[str, list[str]] = {}
    for raw_line in stdout.splitlines():
        fields = raw_line.rstrip("\n").split("\t")
        if not fields or fields[0] not in ENVIRONMENT_KEYS:
            continue
        if fields[0] in values:
            raise ValueError(f"Duplicate provider environment field: {fields[0]}")
        values[fields[0]] = fields[1:]
    if set(values) != set(ENVIRONMENT_KEYS):
        raise ValueError("Provider environment output is incomplete")
    if len(values["path"]) != 1 or len(values["architecture"]) != 1:
        raise ValueError("Provider environment scalar output is invalid")
    if len(values["os"]) != 2:
        raise ValueError("Provider OS output is invalid")
    path = tuple(
        item
        for item in values["path"][0].split(":")
        if item and PurePosixPath(item).is_absolute()
    )
    return ProviderEnvironment(
        path=path,
        architecture=validate_name(values["architecture"][0], "architecture"),
        os_id=validate_name(values["os"][0], "operating system"),
        codename=validate_name(values["os"][1], "operating system codename"),
    )


def parse_apt_file_discovery(
    capability: str,
    stdout: str,
    environment: ProviderEnvironment,
) -> AptFileDiscovery:
    name = validate_name(capability, "capability")
    path_directories = set(environment.path)
    candidates: set[AptFileCandidate] = set()
    rejected: list[dict[str, str]] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = APT_FILE_LINE.fullmatch(line)
        if match is None:
            rejected.append({"line": line, "reason": "malformed"})
            continue
        package, path_value = match.groups()
        path = PurePosixPath(path_value)
        if not path.is_absolute():
            rejected.append(
                {"package": package, "path": path_value, "reason": "non_absolute"}
            )
            continue
        if path.name != name:
            rejected.append(
                {"package": package, "path": str(path), "reason": "basename"}
            )
            continue
        if str(path.parent) not in path_directories:
            rejected.append(
                {"package": package, "path": str(path), "reason": "not_on_path"}
            )
            continue
        normalize_packages([package])
        candidates.add(AptFileCandidate(package, str(path)))
    return AptFileDiscovery(
        capability=name,
        manager="apt-get",
        candidates=tuple(sorted(candidates)),
        rejected=tuple(sorted(rejected, key=lambda item: tuple(sorted(item.items())))),
    )
