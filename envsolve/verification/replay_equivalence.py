from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from typing import Iterable

from packaging.utils import canonicalize_name


@dataclass(frozen=True, order=True)
class DistributionState:
    name: str
    version: str


@dataclass(frozen=True, order=True)
class ProjectDistributionState:
    name: str
    version: str
    metadata_sha256: str
    provenance_kind: str
    provenance_sha256: str


@dataclass(frozen=True)
class EnvironmentSnapshot:
    python_runtime: tuple[tuple[str, str], ...]
    marker_environment: tuple[tuple[str, str], ...]
    installed_distributions: tuple[DistributionState, ...]
    project_distributions: tuple[ProjectDistributionState, ...]

    @property
    def sha256(self) -> str:
        payload = {
            "python_runtime": list(self.python_runtime),
            "marker_environment": list(self.marker_environment),
            "installed_distributions": [item.__dict__ for item in self.installed_distributions],
            "project_distributions": [item.__dict__ for item in self.project_distributions],
        }
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ReplayIdentity:
    image_id: str
    repository_digest: str
    platform: str
    repository: str
    revision: str
    git_tree: str
    bootstrap_sha256: str
    preregistration_sha256: str


@dataclass(frozen=True)
class ReplayObservation:
    identity: ReplayIdentity
    snapshot: EnvironmentSnapshot | None


@dataclass(frozen=True)
class ReplayDifference:
    component: str
    first_only: tuple[str, ...]
    second_only: tuple[str, ...]


@dataclass(frozen=True)
class ReplayDecision:
    passed: bool | None
    reason: str
    first_snapshot_sha256: str | None
    second_snapshot_sha256: str | None
    differences: tuple[ReplayDifference, ...]


def build_snapshot(
    python_runtime: dict[str, str],
    marker_environment: dict[str, str],
    installed_distributions: Iterable[tuple[str, str]],
    project_distributions: Iterable[tuple[str, str, str, str, str]],
) -> EnvironmentSnapshot:
    return EnvironmentSnapshot(
        python_runtime=tuple(sorted((str(key), str(value)) for key, value in python_runtime.items())),
        marker_environment=tuple(
            sorted((str(key), str(value)) for key, value in marker_environment.items())
        ),
        installed_distributions=tuple(
            sorted(
                DistributionState(canonicalize_name(name), str(version))
                for name, version in installed_distributions
            )
        ),
        project_distributions=tuple(
            sorted(
                ProjectDistributionState(
                    canonicalize_name(name),
                    str(version),
                    str(metadata_sha256),
                    str(provenance_kind),
                    str(provenance_sha256),
                )
                for name, version, metadata_sha256, provenance_kind, provenance_sha256 in project_distributions
            )
        ),
    )


def snapshot_from_artifact(value: object) -> EnvironmentSnapshot:
    if not isinstance(value, dict):
        raise ValueError("V6 snapshot must be an object")
    try:
        python_runtime = value["python_runtime"]
        marker_environment = value["marker_environment"]
        installed = value["installed_distributions"]
        projects = value["project_distributions"]
        claimed_sha256 = value["sha256"]
    except KeyError as exc:
        raise ValueError(f"V6 snapshot field missing: {exc.args[0]}") from exc
    if not isinstance(python_runtime, dict) or not isinstance(marker_environment, dict):
        raise ValueError("V6 runtime and marker evidence must be objects")
    if not isinstance(installed, list) or not isinstance(projects, list):
        raise ValueError("V6 distribution evidence must be lists")
    try:
        snapshot = build_snapshot(
            {str(key): str(item) for key, item in python_runtime.items()},
            {str(key): str(item) for key, item in marker_environment.items()},
            ((str(item["name"]), str(item["version"])) for item in installed),
            (
                (
                    str(item["name"]),
                    str(item["version"]),
                    str(item["metadata_sha256"]),
                    str(item["provenance_kind"]),
                    str(item["provenance_sha256"]),
                )
                for item in projects
            ),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("V6 distribution evidence is malformed") from exc
    if claimed_sha256 != snapshot.sha256:
        raise ValueError("V6 snapshot hash mismatch")
    return snapshot


def compare_replays(
    first: ReplayObservation,
    second: ReplayObservation,
) -> ReplayDecision:
    if first.identity != second.identity:
        return ReplayDecision(
            None,
            "replay identities differ",
            first.snapshot.sha256 if first.snapshot is not None else None,
            second.snapshot.sha256 if second.snapshot is not None else None,
            (
                ReplayDifference(
                    "identity",
                    (repr(first.identity),),
                    (repr(second.identity),),
                ),
            ),
        )
    if first.snapshot is None or second.snapshot is None:
        return ReplayDecision(
            None,
            "one or both replay snapshots are missing",
            first.snapshot.sha256 if first.snapshot is not None else None,
            second.snapshot.sha256 if second.snapshot is not None else None,
            (),
        )
    first_sha = first.snapshot.sha256
    second_sha = second.snapshot.sha256
    if first_sha == second_sha:
        return ReplayDecision(
            True,
            "fresh replay environment snapshots are identical",
            first_sha,
            second_sha,
            (),
        )
    differences = _snapshot_differences(first.snapshot, second.snapshot)
    return ReplayDecision(
        False,
        "fresh replay environment snapshots differ",
        first_sha,
        second_sha,
        differences,
    )


def _snapshot_differences(
    first: EnvironmentSnapshot,
    second: EnvironmentSnapshot,
) -> tuple[ReplayDifference, ...]:
    differences = []
    for component, first_values, second_values in (
        ("python_runtime", first.python_runtime, second.python_runtime),
        ("marker_environment", first.marker_environment, second.marker_environment),
        (
            "installed_distributions",
            tuple(f"{item.name}=={item.version}" for item in first.installed_distributions),
            tuple(f"{item.name}=={item.version}" for item in second.installed_distributions),
        ),
        (
            "project_distributions",
            tuple(_project_string(item) for item in first.project_distributions),
            tuple(_project_string(item) for item in second.project_distributions),
        ),
    ):
        first_only, second_only = _counter_delta(first_values, second_values)
        if first_only or second_only:
            differences.append(
                ReplayDifference(component, first_only, second_only)
            )
    return tuple(differences)


def _counter_delta(
    first: Iterable[object], second: Iterable[object]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    first_counter = Counter(repr(item) for item in first)
    second_counter = Counter(repr(item) for item in second)
    first_only = tuple(sorted((first_counter - second_counter).elements()))
    second_only = tuple(sorted((second_counter - first_counter).elements()))
    return first_only, second_only


def _project_string(value: ProjectDistributionState) -> str:
    return "|".join(
        (
            f"{value.name}=={value.version}",
            value.metadata_sha256,
            value.provenance_kind,
            value.provenance_sha256,
        )
    )
