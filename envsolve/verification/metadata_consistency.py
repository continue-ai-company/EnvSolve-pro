from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from packaging.markers import UndefinedEnvironmentName
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version


_HASH = re.compile(r"^[0-9a-f]{64}$")
_EXTRA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_MARKER_KEYS = frozenset(
    {
        "implementation_name",
        "implementation_version",
        "os_name",
        "platform_machine",
        "platform_release",
        "platform_system",
        "platform_version",
        "python_full_version",
        "platform_python_implementation",
        "python_version",
        "sys_platform",
    }
)
_PROVENANCE_KINDS = frozenset({"pep610-direct-url", "legacy-egg-link"})


@dataclass(frozen=True)
class ProjectMetadataEvidence:
    name: str
    version: str
    metadata_sha256: str
    provenance_kind: str
    provenance_sha256: str
    requires_dist: tuple[str, ...]


@dataclass(frozen=True)
class InstalledDistributionObservation:
    name: str
    version: str


@dataclass(frozen=True)
class ResolverCheck:
    argv: tuple[str, ...]
    exit_code: int | None
    stdout_sha256: str
    stderr_sha256: str
    network_disabled: bool


@dataclass(frozen=True)
class ConsistencyIssue:
    kind: str
    requirement: str | None
    detail: str


@dataclass(frozen=True)
class MetadataConsistencyDecision:
    passed: bool | None
    reason: str
    active_requirements: tuple[str, ...]
    issues: tuple[ConsistencyIssue, ...]


def evaluate_metadata_consistency(
    project: ProjectMetadataEvidence | None,
    installed: tuple[InstalledDistributionObservation, ...] | None,
    marker_environment: Mapping[str, str] | None,
    selected_extras: tuple[str, ...] | None,
    resolver: ResolverCheck | None,
) -> MetadataConsistencyDecision:
    if any(value is None for value in (project, installed, marker_environment, selected_extras, resolver)):
        return MetadataConsistencyDecision(None, "required V1 evidence missing", (), ())
    assert project is not None
    assert installed is not None
    assert marker_environment is not None
    assert selected_extras is not None
    assert resolver is not None
    if not _valid_resolver_evidence(resolver):
        return MetadataConsistencyDecision(None, "resolver evidence invalid", (), ())
    if not _valid_project_evidence(project):
        issue = ConsistencyIssue("invalid-project-metadata", None, "project provenance or metadata is invalid")
        return MetadataConsistencyDecision(False, "project metadata invalid", (), (issue,))
    if not _MARKER_KEYS.issubset(marker_environment):
        return MetadataConsistencyDecision(None, "marker environment incomplete", (), ())
    if any(not _EXTRA.fullmatch(extra) for extra in selected_extras):
        issue = ConsistencyIssue("invalid-extra", None, "selected extra name is invalid")
        return MetadataConsistencyDecision(False, "selected extras invalid", (), (issue,))

    installed_by_name: dict[str, list[InstalledDistributionObservation]] = {}
    issues = []
    for item in installed:
        name = canonicalize_name(item.name)
        installed_by_name.setdefault(name, []).append(item)
    active = []
    parsed_requirements = []
    for raw in project.requires_dist:
        try:
            requirement = Requirement(raw)
        except InvalidRequirement:
            issues.append(ConsistencyIssue("invalid-requirement", raw, "Requires-Dist is malformed"))
            continue
        try:
            applies = _requirement_applies(requirement, marker_environment, selected_extras)
        except UndefinedEnvironmentName:
            return MetadataConsistencyDecision(None, "marker environment incomplete", tuple(active), tuple(issues))
        if applies:
            active.append(raw)
            parsed_requirements.append((raw, requirement))
    for raw, requirement in parsed_requirements:
        name = canonicalize_name(requirement.name)
        candidates = installed_by_name.get(name, [])
        if not candidates:
            issues.append(ConsistencyIssue("missing-distribution", raw, f"{name} is not installed"))
            continue
        if len(candidates) != 1:
            issues.append(ConsistencyIssue("ambiguous-distribution", raw, f"{name} has multiple observations"))
            continue
        try:
            version = Version(candidates[0].version)
        except InvalidVersion:
            issues.append(
                ConsistencyIssue(
                    "invalid-installed-version",
                    raw,
                    f"{name} has an invalid version",
                )
            )
            continue
        if requirement.specifier and not requirement.specifier.contains(version):
            issues.append(
                ConsistencyIssue(
                    "incompatible-version",
                    raw,
                    f"{name} {version} does not satisfy {requirement.specifier}",
                )
            )
    if issues:
        return MetadataConsistencyDecision(False, "metadata or installed state conflict", tuple(active), tuple(issues))
    if resolver.exit_code != 0:
        issue = ConsistencyIssue(
            "resolver-conflict",
            None,
            "environment-wide pip check conflict is not attributable to the project closure",
        )
        return MetadataConsistencyDecision(
            None,
            "resolver conflict requires project-scoped attribution",
            tuple(active),
            (issue,),
        )
    return MetadataConsistencyDecision(True, "metadata, installed state, and resolver agree", tuple(active), ())


def _valid_project_evidence(value: ProjectMetadataEvidence) -> bool:
    try:
        Version(value.version)
    except InvalidVersion:
        return False
    return (
        bool(value.name.strip())
        and bool(_HASH.fullmatch(value.metadata_sha256))
        and value.provenance_kind in _PROVENANCE_KINDS
        and bool(_HASH.fullmatch(value.provenance_sha256))
    )


def _valid_resolver_evidence(value: ResolverCheck) -> bool:
    return (
        len(value.argv) == 4
        and value.argv[1:] == ("-m", "pip", "check")
        and bool(value.argv[0])
        and value.exit_code is not None
        and value.network_disabled
        and bool(_HASH.fullmatch(value.stdout_sha256))
        and bool(_HASH.fullmatch(value.stderr_sha256))
    )


def _requirement_applies(
    requirement: Requirement,
    marker_environment: Mapping[str, str],
    selected_extras: tuple[str, ...],
) -> bool:
    if requirement.marker is None:
        return True
    contexts = ("", *sorted(set(selected_extras)))
    return any(
        requirement.marker.evaluate({**marker_environment, "extra": extra})
        for extra in contexts
    )
