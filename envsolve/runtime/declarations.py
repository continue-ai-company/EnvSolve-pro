from __future__ import annotations

from configparser import ConfigParser, Error as ConfigError
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable

from packaging.requirements import InvalidRequirement, Requirement

from envsolve.constraints import InitialConstraintEvidence

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - selected by the Python runtime
    try:
        import tomli as tomllib
    except ModuleNotFoundError:  # Local Python 3.9 may expose tomli through pip.
        from pip._vendor import tomli as tomllib  # type: ignore[no-redef]


REPOSITORY_DECLARATION_SCHEMA = "envsolve-repository-declarations-v1"
_INLINE_COMMENT = re.compile(r"\s+#.*$")


@dataclass(frozen=True)
class DeclarationDiagnostic:
    path: str
    reason: str
    line: int | None = None
    declaration_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "reason": self.reason,
            "line": self.line,
            "declaration_sha256": self.declaration_sha256,
        }


@dataclass(frozen=True)
class RepositoryConstraintInventory:
    evidence: tuple[InitialConstraintEvidence, ...] = ()
    diagnostics: tuple[DeclarationDiagnostic, ...] = ()
    files_observed: tuple[str, ...] = ()
    source_bytes: int = 0
    schema: str = field(default=REPOSITORY_DECLARATION_SCHEMA, init=False)

    def summary(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "evidence_count": len(self.evidence),
            "diagnostic_count": len(self.diagnostics),
            "files_observed": list(self.files_observed),
            "source_bytes": self.source_bytes,
            "diagnostics": [item.to_dict() for item in self.diagnostics[:100]],
        }


class _Collector:
    def __init__(self, max_declarations: int, max_diagnostics: int = 1_000) -> None:
        self.max_declarations = max_declarations
        self.max_diagnostics = max_diagnostics
        self.evidence: dict[str, InitialConstraintEvidence] = {}
        self.diagnostics: list[DeclarationDiagnostic] = []
        self.bound_reported = False
        self.diagnostic_bound_reported = False

    @staticmethod
    def _declaration_hash(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def diagnostic(
        self,
        path: str,
        reason: str,
        *,
        line: int | None = None,
        raw: str | None = None,
    ) -> None:
        if len(self.diagnostics) >= self.max_diagnostics:
            if not self.diagnostic_bound_reported:
                self.diagnostics.append(
                    DeclarationDiagnostic(path, "diagnostic-bound-exceeded")
                )
                self.diagnostic_bound_reported = True
            return
        self.diagnostics.append(
            DeclarationDiagnostic(
                path,
                reason,
                line,
                self._declaration_hash(raw) if raw is not None else None,
            )
        )

    def requirement(
        self,
        raw: str,
        *,
        path: str,
        source_sha256: str,
        line: int | None = None,
    ) -> None:
        if len(self.evidence) >= self.max_declarations:
            if not self.bound_reported:
                self.diagnostic(path, "declaration-bound-exceeded")
                self.bound_reported = True
            return
        if len(raw) > 4_096:
            self.diagnostic(path, "declaration-too-long", line=line, raw=raw)
            return
        try:
            requirement = Requirement(raw)
        except InvalidRequirement:
            self.diagnostic(path, "invalid-pep508-requirement", line=line, raw=raw)
            return
        if requirement.marker is not None:
            self.diagnostic(path, "environment-marker-unresolved", line=line, raw=raw)
            return
        value: dict[str, Any] = {
            "name": requirement.name,
            "source_path": path,
            "source_sha256": source_sha256,
            "declared_requirement": str(requirement),
            "extras": sorted(requirement.extras),
        }
        if requirement.specifier:
            value["specifier"] = str(requirement.specifier)
        else:
            value["present"] = True
        semantic = {
            "kind": "package-requirement",
            "source": f"repository-declaration:{path}",
            "value": value,
        }
        digest = hashlib.sha256(
            json.dumps(
                semantic, ensure_ascii=True, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")
        ).hexdigest()
        evidence = InitialConstraintEvidence(
            evidence_id=f"repository-requirement-{digest[:24]}",
            kind=str(semantic["kind"]),
            source=str(semantic["source"]),
            value=value,
        )
        self.evidence[evidence.evidence_id] = evidence


def collect_repository_constraints(
    root: Path,
    *,
    max_files: int = 32,
    max_source_bytes: int = 2_000_000,
    max_declarations: int = 1_000,
) -> RepositoryConstraintInventory:
    """Read standard, project-owned dependency declarations without executing code."""
    if min(max_files, max_source_bytes, max_declarations) <= 0:
        raise ValueError("Repository declaration bounds must be positive")
    resolved = root.resolve()
    if not resolved.is_dir():
        raise ValueError("Repository declaration root must be a directory")

    candidates = [resolved / "pyproject.toml", resolved / "setup.cfg"]
    candidates.extend(sorted(resolved.glob("requirements*.txt")))
    paths = tuple(
        path for path in candidates if path.is_file() and not path.is_symlink()
    )
    collector = _Collector(max_declarations)
    observed: list[str] = []
    total_bytes = 0
    parsers: dict[str, Callable[[str, str, str, _Collector], None]] = {
        "pyproject.toml": _parse_pyproject,
        "setup.cfg": _parse_setup_cfg,
    }
    for path in paths[:max_files]:
        relative = path.relative_to(resolved).as_posix()
        if total_bytes + path.stat().st_size > max_source_bytes:
            collector.diagnostic(relative, "source-byte-bound-exceeded")
            continue
        payload = path.read_bytes()
        if total_bytes + len(payload) > max_source_bytes:
            collector.diagnostic(relative, "source-byte-bound-exceeded")
            continue
        total_bytes += len(payload)
        observed.append(relative)
        source_sha256 = hashlib.sha256(payload).hexdigest()
        content = payload.decode("utf-8", errors="replace")
        parser = parsers.get(path.name, _parse_requirements)
        parser(content, relative, source_sha256, collector)
    if len(paths) > max_files:
        collector.diagnostic(".", "file-bound-exceeded")
    return RepositoryConstraintInventory(
        evidence=tuple(collector.evidence[key] for key in sorted(collector.evidence)),
        diagnostics=tuple(collector.diagnostics),
        files_observed=tuple(observed),
        source_bytes=total_bytes,
    )


def _parse_pyproject(
    content: str,
    path: str,
    source_sha256: str,
    collector: _Collector,
) -> None:
    try:
        data = tomllib.loads(content)
    except (ValueError, TypeError):
        collector.diagnostic(path, "invalid-toml")
        return
    project = data.get("project")
    if project is None:
        return
    if not isinstance(project, dict):
        collector.diagnostic(path, "invalid-pep621-project-table")
        return
    dependencies = project.get("dependencies", [])
    if not isinstance(dependencies, list) or not all(
        isinstance(item, str) for item in dependencies
    ):
        collector.diagnostic(path, "invalid-pep621-dependencies")
        return
    for raw in dependencies:
        collector.requirement(raw.strip(), path=path, source_sha256=source_sha256)


def _parse_setup_cfg(
    content: str,
    path: str,
    source_sha256: str,
    collector: _Collector,
) -> None:
    parser = ConfigParser(interpolation=None, strict=True)
    try:
        parser.read_string(content)
    except ConfigError:
        collector.diagnostic(path, "invalid-setup-cfg")
        return
    if not parser.has_option("options", "install_requires"):
        return
    for raw in parser.get("options", "install_requires").splitlines():
        value = raw.strip()
        if value:
            collector.requirement(value, path=path, source_sha256=source_sha256)


def _parse_requirements(
    content: str,
    path: str,
    source_sha256: str,
    collector: _Collector,
) -> None:
    for line_number, raw in enumerate(content.splitlines(), start=1):
        value = _INLINE_COMMENT.sub("", raw).strip()
        if not value or value.startswith("#"):
            continue
        if value.startswith("-") or value.endswith("\\"):
            collector.diagnostic(
                path,
                "unsupported-requirements-directive",
                line=line_number,
                raw=value,
            )
            continue
        collector.requirement(
            value,
            path=path,
            source_sha256=source_sha256,
            line=line_number,
        )
