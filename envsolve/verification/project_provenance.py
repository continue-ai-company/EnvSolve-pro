from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib import metadata
import json
from pathlib import Path
import re
import site
import sys
from typing import Any, Iterable
from urllib.parse import unquote, urlparse


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def direct_url_project_path(raw: str | None) -> Path | None:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
        parsed = urlparse(str(value["url"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
        return None
    return Path(unquote(parsed.path)).resolve()


def is_project_distribution(raw: str | None, project_root: Path) -> bool:
    candidate = direct_url_project_path(raw)
    if candidate is None:
        return False
    root = project_root.resolve()
    return candidate == root or root in candidate.parents


def canonical_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def legacy_egg_link_target(raw: str) -> Path | None:
    first = next((line.strip() for line in raw.splitlines() if line.strip()), "")
    candidate = Path(first)
    return candidate.resolve() if first and candidate.is_absolute() else None


@dataclass(frozen=True)
class ProjectDistributionMatch:
    distribution: Any
    provenance_kind: str
    provenance_sha256: str


def installed_egg_links() -> tuple[Path, ...]:
    roots = {Path(value) for value in sys.path if value}
    roots.update(Path(value) for value in site.getsitepackages())
    roots.add(Path(site.getusersitepackages()))
    links = []
    for root in sorted(roots):
        try:
            links.extend(root.glob("*.egg-link"))
        except OSError:
            continue
    return tuple(sorted(set(links)))


def find_project_distributions(
    project_root: Path,
    installed_distributions: Iterable[Any] | None = None,
    project_owned_distributions: Iterable[Any] | None = None,
    egg_links: Iterable[Path] | None = None,
) -> tuple[ProjectDistributionMatch, ...]:
    root = project_root.resolve()
    installed = tuple(
        metadata.distributions()
        if installed_distributions is None
        else installed_distributions
    )
    project_owned = tuple(
        metadata.distributions(path=[str(root)])
        if project_owned_distributions is None
        else project_owned_distributions
    )
    matches: dict[tuple[str, str], ProjectDistributionMatch] = {}
    for distribution in installed:
        raw = distribution.read_text("direct_url.json")
        if not is_project_distribution(raw, root):
            continue
        key = (
            canonical_distribution_name(str(distribution.metadata["Name"])),
            str(distribution.version),
        )
        matches[key] = ProjectDistributionMatch(
            distribution, "pep610-direct-url", sha_bytes(raw.encode("utf-8"))
        )

    owned_by_name: dict[str, list[Any]] = {}
    for distribution in project_owned:
        name = canonical_distribution_name(str(distribution.metadata["Name"]))
        owned_by_name.setdefault(name, []).append(distribution)
    links = installed_egg_links() if egg_links is None else tuple(egg_links)
    for link in links:
        try:
            raw = link.read_text(encoding="utf-8")
        except OSError:
            continue
        target = legacy_egg_link_target(raw)
        if target is None or not (target == root or root in target.parents):
            continue
        link_name = canonical_distribution_name(link.name[: -len(".egg-link")])
        candidates = owned_by_name.get(link_name, [])
        if len(candidates) != 1:
            continue
        distribution = candidates[0]
        key = (link_name, str(distribution.version))
        matches.setdefault(
            key,
            ProjectDistributionMatch(
                distribution, "legacy-egg-link", sha_bytes(raw.encode("utf-8"))
            ),
        )
    return tuple(
        sorted(
            matches.values(),
            key=lambda item: (
                canonical_distribution_name(str(item.distribution.metadata["Name"])),
                str(item.distribution.version),
            ),
        )
    )
