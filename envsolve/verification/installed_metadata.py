from __future__ import annotations

import hashlib
from importlib import metadata
from typing import Protocol

from envsolve.verification.smoke import ConsoleEntryPoint, DistributionSnapshot


_MODERN_SNAPSHOT_FILES = ("METADATA", "top_level.txt", "entry_points.txt")
_LEGACY_SNAPSHOT_FILES = ("PKG-INFO", "top_level.txt", "entry_points.txt")


class InstalledDistribution(Protocol):
    version: str
    entry_points: object
    metadata: object

    def read_text(self, filename: str) -> str | None: ...


def collect_distribution_snapshot(
    distribution_name: str,
    installed: InstalledDistribution | None = None,
) -> DistributionSnapshot:
    distribution = installed or metadata.distribution(distribution_name)
    metadata_source = installed_metadata_source(distribution)
    if metadata_source is None:
        raise ValueError("installed distribution has no METADATA or PKG-INFO")
    snapshot_files = (
        _MODERN_SNAPSHOT_FILES if metadata_source == "METADATA" else _LEGACY_SNAPSHOT_FILES
    )
    contents = {name: distribution.read_text(name) for name in snapshot_files}
    digest = _snapshot_hash(contents, snapshot_files)
    top_level = tuple(
        sorted(
            {
                line.strip()
                for line in (contents["top_level.txt"] or "").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            }
        )
    )
    entries = tuple(
        sorted(
            (
                ConsoleEntryPoint(str(item.name), str(item.value))
                for item in distribution.entry_points  # type: ignore[union-attr]
                if str(item.group) == "console_scripts"
            ),
            key=lambda item: (item.name, item.target),
        )
    )
    project_name = str(distribution.metadata["Name"])  # type: ignore[index]
    return DistributionSnapshot(
        name=project_name,
        version=str(distribution.version),
        metadata_sha256=digest,
        top_level_modules=top_level,
        console_scripts=entries,
    )


def installed_metadata_source(distribution: InstalledDistribution) -> str | None:
    if distribution.read_text("METADATA") is not None:
        return "METADATA"
    if distribution.read_text("PKG-INFO") is not None:
        return "PKG-INFO"
    return None


def _snapshot_hash(
    contents: dict[str, str | None], snapshot_files: tuple[str, ...]
) -> str:
    digest = hashlib.sha256()
    for name in snapshot_files:
        payload = (contents[name] or "").encode("utf-8")
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name.encode("ascii"))
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()
