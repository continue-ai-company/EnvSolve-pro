from __future__ import annotations

from email.parser import Parser
from typing import Any, Iterable

from envsolve.verification.installed_metadata import (
    collect_distribution_snapshot,
    installed_metadata_source,
)
from envsolve.verification.metadata_consistency import (
    InstalledDistributionObservation,
    ProjectMetadataEvidence,
)
from envsolve.verification.project_provenance import (
    ProjectDistributionMatch,
    canonical_distribution_name,
)


def collect_project_evidence(
    match: ProjectDistributionMatch,
) -> tuple[ProjectMetadataEvidence, str]:
    distribution = match.distribution
    source = installed_metadata_source(distribution)
    if source is None:
        raise ValueError("installed project distribution has no metadata")
    raw = distribution.read_text(source)
    if raw is None:
        raise ValueError("installed project metadata disappeared during collection")
    parsed = Parser().parsestr(raw)
    name = str(parsed.get("Name") or "").strip()
    version = str(parsed.get("Version") or "").strip()
    if not name or not version:
        raise ValueError("installed project metadata has no Name or Version")
    snapshot = collect_distribution_snapshot(name, distribution)
    if canonical_distribution_name(snapshot.name) != canonical_distribution_name(name):
        raise ValueError("installed project metadata name is internally inconsistent")
    if snapshot.version != version:
        raise ValueError("installed project metadata version is internally inconsistent")
    requirements = tuple(str(item) for item in (parsed.get_all("Requires-Dist") or ()))
    return (
        ProjectMetadataEvidence(
            name=name,
            version=version,
            metadata_sha256=snapshot.metadata_sha256,
            provenance_kind=match.provenance_kind,
            provenance_sha256=match.provenance_sha256,
            requires_dist=requirements,
        ),
        source,
    )


def collect_installed_observations(
    distributions: Iterable[Any],
) -> tuple[tuple[InstalledDistributionObservation, ...], tuple[dict[str, str], ...]]:
    observations = []
    errors = []
    for index, distribution in enumerate(distributions):
        try:
            name = str(distribution.metadata["Name"]).strip()
            version = str(distribution.version).strip()
            if not name or not version:
                raise ValueError("empty Name or Version")
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(
                {
                    "kind": "installed-distribution-unreadable",
                    "distribution_index": str(index),
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        observations.append(InstalledDistributionObservation(name, version))
    return (
        tuple(
            sorted(
                observations,
                key=lambda item: (canonical_distribution_name(item.name), item.version),
            )
        ),
        tuple(errors),
    )
