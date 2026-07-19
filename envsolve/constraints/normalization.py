from __future__ import annotations

import re
from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from envsolve.constraints.models import (
    ConstraintDomain,
    ConstraintPredicate,
    ConstraintRole,
    NormalizedConstraint,
)


PYTHON_REQUIREMENT_KINDS = {
    "python-requirement",
    "python-requires",
    "runtime-requirement",
}
PYTHON_OBSERVATION_KINDS = {"python-observation", "runtime-observation"}
PYTHON_MISMATCH_PATTERNS = (
    re.compile(
        r"requires a different Python:\s*"
        r"(?P<version>[0-9]+(?:\.[0-9]+)*)\s+not in\s+"
        r"['\"](?P<specifier>[^'\"]+)['\"]",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*Current Python version \("
        r"(?P<version>[0-9]+(?:\.[0-9]+)*)\) "
        r"is not allowed by the project \("
        r"(?P<specifier>[^()\r\n]+)\)\.?\s*$",
        re.IGNORECASE | re.MULTILINE,
    ),
)
EXECUTABLE_NOT_FOUND = re.compile(
    r"(?:Error:\s*)?([A-Za-z0-9_.+-]+) executable not found",
    re.IGNORECASE,
)
MODULE_NOT_FOUND = re.compile(
    r"(?:ModuleNotFoundError:\s*)?No module named ['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} evidence value must be an object")
    return value


def _python_mismatches(text: str) -> tuple[tuple[str, str], ...]:
    mismatches: set[tuple[str, str]] = set()
    for pattern in PYTHON_MISMATCH_PATTERNS:
        for match in pattern.finditer(text):
            version = match.group("version").strip()
            specifier = match.group("specifier").strip()
            try:
                observed = Version(version)
                allowed = SpecifierSet(specifier)
            except (InvalidVersion, InvalidSpecifier):
                continue
            if observed not in allowed:
                mismatches.add((version, specifier))
    return tuple(sorted(mismatches))


class EvidenceNormalizer:
    def normalize(
        self,
        evidence_id: str,
        evidence: dict[str, Any],
    ) -> tuple[NormalizedConstraint, ...]:
        kind = str(evidence.get("kind", "")).strip().lower()
        value = evidence.get("value")
        confidence = float(evidence.get("confidence", 1.0))
        if kind in PYTHON_REQUIREMENT_KINDS:
            data = value if isinstance(value, dict) else {"specifier": value}
            return (
                NormalizedConstraint(
                    ConstraintDomain.RUNTIME,
                    str(data.get("name", "python")),
                    ConstraintPredicate.VERSION,
                    str(data["specifier"]),
                    ConstraintRole.REQUIREMENT,
                    (evidence_id,),
                    confidence,
                ),
            )
        if kind in PYTHON_OBSERVATION_KINDS:
            data = _mapping(value, kind)
            return (
                NormalizedConstraint(
                    ConstraintDomain.RUNTIME,
                    str(data.get("name", "python")),
                    ConstraintPredicate.VERSION,
                    str(data["version"]),
                    ConstraintRole.FACT,
                    (evidence_id,),
                    confidence,
                ),
            )
        if kind in {"package-requirement", "package-observation"}:
            data = _mapping(value, kind)
            role = (
                ConstraintRole.REQUIREMENT
                if kind.endswith("requirement")
                else ConstraintRole.FACT
            )
            if "version" in data or "specifier" in data:
                if role == ConstraintRole.REQUIREMENT:
                    version = data.get("specifier")
                    if version is None:
                        version = f"=={data['version']}"
                else:
                    if "version" not in data:
                        raise ValueError("Package observations require a version")
                    version = data["version"]
                return (
                    NormalizedConstraint(
                        ConstraintDomain.PACKAGE,
                        str(data["name"]),
                        ConstraintPredicate.VERSION,
                        str(version),
                        role,
                        (evidence_id,),
                        confidence,
                    ),
                )
            return self._presence(
                ConstraintDomain.PACKAGE,
                role,
                evidence_id,
                data,
                confidence,
            )
        if kind in {
            "capability-requirement",
            "capability-observation",
            "module-requirement",
            "module-observation",
        }:
            data = _mapping(value, kind)
            domain = (
                ConstraintDomain.CAPABILITY
                if kind.startswith("capability")
                else ConstraintDomain.MODULE
            )
            role = (
                ConstraintRole.REQUIREMENT
                if kind.endswith("requirement")
                else ConstraintRole.FACT
            )
            return self._presence(domain, role, evidence_id, data, confidence)
        if kind == "platform-requirement" or kind == "platform-observation":
            data = _mapping(value, kind)
            role = (
                ConstraintRole.REQUIREMENT
                if kind.endswith("requirement")
                else ConstraintRole.FACT
            )
            return (
                NormalizedConstraint(
                    ConstraintDomain.PLATFORM,
                    str(data.get("name", "platform")),
                    ConstraintPredicate.EQUALS,
                    str(data["value"]),
                    role,
                    (evidence_id,),
                    confidence,
                ),
            )
        if kind == "action-result":
            return self._action_result(evidence_id, value, confidence)
        return ()

    @staticmethod
    def _presence(
        domain: ConstraintDomain,
        role: ConstraintRole,
        evidence_id: str,
        data: dict[str, Any],
        confidence: float,
    ) -> tuple[NormalizedConstraint, ...]:
        present = data.get("present", True)
        if not isinstance(present, bool):
            raise ValueError("Presence evidence 'present' must be boolean")
        return (
            NormalizedConstraint(
                domain,
                str(data["name"]),
                ConstraintPredicate.PRESENT,
                present,
                role,
                (evidence_id,),
                confidence,
            ),
        )

    def _action_result(
        self,
        evidence_id: str,
        value: Any,
        confidence: float,
    ) -> tuple[NormalizedConstraint, ...]:
        data = _mapping(value, "action-result")
        exit_code = data.get("exit_code")
        if isinstance(exit_code, bool) or not isinstance(exit_code, int) or exit_code == 0:
            return ()
        derived_confidence = (
            confidence
            if data.get("deterministic_counterexample") is True
            else min(confidence, 0.5)
        )
        text = f"{data.get('stdout', '')}\n{data.get('stderr', '')}"
        constraints: list[NormalizedConstraint] = []
        for version, specifier in _python_mismatches(text):
            constraints.extend(
                [
                    NormalizedConstraint(
                        ConstraintDomain.RUNTIME,
                        "python",
                        ConstraintPredicate.VERSION,
                        specifier,
                        ConstraintRole.REQUIREMENT,
                        (evidence_id,),
                        confidence,
                    ),
                    NormalizedConstraint(
                        ConstraintDomain.RUNTIME,
                        "python",
                        ConstraintPredicate.VERSION,
                        version,
                        ConstraintRole.FACT,
                        (evidence_id,),
                        confidence,
                    ),
                ]
            )
        for match in EXECUTABLE_NOT_FOUND.finditer(text):
            name = match.group(1)
            constraints.extend(
                [
                    NormalizedConstraint(
                        ConstraintDomain.CAPABILITY,
                        name,
                        ConstraintPredicate.PRESENT,
                        True,
                        ConstraintRole.REQUIREMENT,
                        (evidence_id,),
                        derived_confidence,
                    ),
                    NormalizedConstraint(
                        ConstraintDomain.CAPABILITY,
                        name,
                        ConstraintPredicate.PRESENT,
                        False,
                        ConstraintRole.FACT,
                        (evidence_id,),
                        derived_confidence,
                    ),
                ]
            )
        for match in MODULE_NOT_FOUND.finditer(text):
            constraints.extend(
                [
                    NormalizedConstraint(
                        ConstraintDomain.MODULE,
                        match.group(1),
                        ConstraintPredicate.PRESENT,
                        True,
                        ConstraintRole.REQUIREMENT,
                        (evidence_id,),
                        derived_confidence,
                    ),
                    NormalizedConstraint(
                        ConstraintDomain.MODULE,
                        match.group(1),
                        ConstraintPredicate.PRESENT,
                        False,
                        ConstraintRole.FACT,
                        (evidence_id,),
                        derived_confidence,
                    ),
                ]
            )
        unique = {item.constraint_id: item for item in constraints}
        return tuple(unique[key] for key in sorted(unique))
