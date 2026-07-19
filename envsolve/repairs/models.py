from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Any, Mapping

from packaging.version import InvalidVersion, Version

from envsolve.constraints import (
    ConstraintDomain,
    ConstraintPredicate,
    ConstraintRole,
    NormalizedConstraint,
)
from envsolve.solver import ActionSpec


REPAIR_SCHEMA_VERSION = "1.0.0"


class RepairKind(str, Enum):
    RUNTIME_SELECTION = "runtime_selection"
    SYSTEM_CAPABILITY_INSTALL = "system_capability_install"
    PYTHON_MODULE_INSTALL = "python_module_install"


class RepairRisk(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class ProbeKind(str, Enum):
    RUNTIME_VERSION = "runtime_version"
    CAPABILITY_PRESENCE = "capability_presence"
    MODULE_PRESENCE = "module_presence"


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _fact_effect(fact: NormalizedConstraint) -> dict[str, Any]:
    return {
        "domain": fact.domain.value,
        "subject": fact.subject,
        "predicate": fact.predicate.value,
        "value": fact.value,
        "confidence": fact.confidence,
    }


@dataclass(frozen=True)
class RepairContext:
    runtime_manager: str | None = None
    runtime_root: str | None = None
    available_python_versions: tuple[str, ...] = ()
    system_package_manager: str | None = None
    capability_packages: Mapping[str, tuple[str, ...]] | None = None
    module_distributions: Mapping[str, tuple[str, ...]] | None = None
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        runtime_manager = self.runtime_manager.lower() if self.runtime_manager else None
        runtime_root = self.runtime_root
        system_manager = (
            self.system_package_manager.lower()
            if self.system_package_manager
            else None
        )
        if runtime_manager not in {None, "pyenv"}:
            raise ValueError(f"Unsupported runtime manager: {runtime_manager}")
        if runtime_root is not None and (
            not runtime_root.startswith("/") or "\n" in runtime_root or "\r" in runtime_root
        ):
            raise ValueError(f"Runtime root must be an absolute path: {runtime_root!r}")
        if system_manager not in {None, "apt", "apt-get", "apk", "brew", "dnf", "yum"}:
            raise ValueError(f"Unsupported system package manager: {system_manager}")
        versions: list[str] = []
        for value in self.available_python_versions:
            try:
                versions.append(str(Version(value)))
            except InvalidVersion as exc:
                raise ValueError(f"Invalid available Python version: {value!r}") from exc
        capability_packages = {
            str(name).lower(): tuple(sorted(set(packages)))
            for name, packages in (self.capability_packages or {}).items()
        }
        module_distributions = {
            str(name).lower(): tuple(sorted(set(packages)))
            for name, packages in (self.module_distributions or {}).items()
        }
        object.__setattr__(self, "runtime_manager", runtime_manager)
        object.__setattr__(self, "runtime_root", runtime_root)
        object.__setattr__(self, "system_package_manager", system_manager)
        object.__setattr__(
            self,
            "available_python_versions",
            tuple(sorted(set(versions), key=Version)),
        )
        object.__setattr__(self, "capability_packages", capability_packages)
        object.__setattr__(self, "module_distributions", module_distributions)
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_manager": self.runtime_manager,
            "runtime_root": self.runtime_root,
            "available_python_versions": list(self.available_python_versions),
            "system_package_manager": self.system_package_manager,
            "capability_packages": {
                key: list(value)
                for key, value in sorted((self.capability_packages or {}).items())
            },
            "module_distributions": {
                key: list(value)
                for key, value in sorted((self.module_distributions or {}).items())
            },
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True)
class ProbeObservation:
    evidence_kind: str
    evidence_value: dict[str, Any]
    fact: NormalizedConstraint


@dataclass(frozen=True)
class VerificationProbe:
    kind: ProbeKind
    command: str
    expected_fact: NormalizedConstraint

    def __post_init__(self) -> None:
        if self.expected_fact.role != ConstraintRole.FACT:
            raise ValueError("Verification probe expected value must be a fact")
        if not self.command.strip():
            raise ValueError("Verification probe command cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "command": self.command,
            "expected_fact": _fact_effect(self.expected_fact),
        }

    def parse_action(self, action: dict[str, Any]) -> ProbeObservation:
        exit_code = action.get("exit_code")
        if isinstance(exit_code, bool) or not isinstance(exit_code, int):
            raise ValueError("Verification action has no integer exit code")
        observation = action.get("observation")
        if not isinstance(observation, dict):
            raise ValueError("Verification action has no observation")
        stdout = str(observation.get("stdout", ""))
        stderr = str(observation.get("stderr", ""))
        if self.kind == ProbeKind.RUNTIME_VERSION:
            match = re.search(
                r"\bPython\s+([0-9]+(?:\.[0-9]+){1,3}(?:[-+._A-Za-z0-9]*)?)",
                f"{stdout}\n{stderr}",
            )
            if exit_code != 0 or match is None:
                raise ValueError("Runtime verification did not report a Python version")
            value: str | bool = str(Version(match.group(1)))
            evidence_kind = "runtime-observation"
            evidence_value = {
                "name": self.expected_fact.subject,
                "version": value,
            }
        elif self.kind == ProbeKind.CAPABILITY_PRESENCE:
            value = exit_code == 0 and bool(stdout.strip())
            evidence_kind = "capability-observation"
            evidence_value = {
                "name": self.expected_fact.subject,
                "present": value,
            }
        elif self.kind == ProbeKind.MODULE_PRESENCE:
            value = exit_code == 0
            evidence_kind = "module-observation"
            evidence_value = {
                "name": self.expected_fact.subject,
                "present": value,
            }
        else:
            raise ValueError(f"Unsupported verification probe: {self.kind.value}")
        fact = NormalizedConstraint(
            domain=self.expected_fact.domain,
            subject=self.expected_fact.subject,
            predicate=self.expected_fact.predicate,
            value=value,
            role=ConstraintRole.FACT,
            evidence_ids=(),
            confidence=1.0,
        )
        return ProbeObservation(evidence_kind, evidence_value, fact)


@dataclass(frozen=True)
class RepairPlan:
    kind: RepairKind
    source_conflict_ids: tuple[str, ...]
    source_constraint_ids: tuple[str, ...]
    supersede_constraint_ids: tuple[str, ...]
    proposed_fact: NormalizedConstraint
    mutation_action_type: str
    mutation_command: str
    rationale: str
    risk: RepairRisk
    probe: VerificationProbe
    supporting_evidence_ids: tuple[str, ...] = ()
    prerequisite_constraint_ids: tuple[str, ...] = ()
    rollback_command: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "source_conflict_ids",
            "source_constraint_ids",
            "supersede_constraint_ids",
            "supporting_evidence_ids",
            "prerequisite_constraint_ids",
        ):
            object.__setattr__(
                self,
                field_name,
                tuple(sorted(set(getattr(self, field_name)))),
            )
        if self.proposed_fact.role != ConstraintRole.FACT:
            raise ValueError("Repair proposed effect must be a fact")
        if self.probe.expected_fact.semantic_dict() != self.proposed_fact.semantic_dict():
            raise ValueError("Repair probe must verify the proposed fact")
        if not self.mutation_action_type.strip() or not self.mutation_command.strip():
            raise ValueError("Repair mutation action type and command are required")
        if not self.source_conflict_ids or not self.supersede_constraint_ids:
            raise ValueError("Repair must identify a conflict and replaced facts")
        if not self.supporting_evidence_ids:
            raise ValueError("Repair context must cite supporting evidence")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": REPAIR_SCHEMA_VERSION,
            "kind": self.kind.value,
            "source_conflict_ids": list(self.source_conflict_ids),
            "source_constraint_ids": list(self.source_constraint_ids),
            "supersede_constraint_ids": list(self.supersede_constraint_ids),
            "proposed_fact": _fact_effect(self.proposed_fact),
            "mutation_action_type": self.mutation_action_type,
            "mutation_command": self.mutation_command,
            "risk": self.risk.value,
            "probe": self.probe.to_dict(),
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
            "prerequisite_constraint_ids": list(self.prerequisite_constraint_ids),
            "rollback_command": self.rollback_command,
        }

    @property
    def repair_id(self) -> str:
        digest = hashlib.sha256(
            _canonical_json(self.semantic_dict()).encode("utf-8")
        ).hexdigest()[:16]
        return f"repair-{self.kind.value}-{digest}"

    @property
    def mutation_action_id(self) -> str:
        return f"{self.repair_id}-apply"

    @property
    def verification_action_id(self) -> str:
        return f"{self.repair_id}-verify"

    @property
    def verification_evidence_id(self) -> str:
        return f"evidence-{self.repair_id}-verification"

    def mutation_action(self) -> ActionSpec:
        return ActionSpec(
            action_type=self.mutation_action_type,
            command=self.mutation_command,
            rationale=self.rationale,
            preconditions=self.prerequisite_constraint_ids,
            action_id=self.mutation_action_id,
            metadata={
                "mutates_environment": True,
                "proposed_facts": [_fact_effect(self.proposed_fact)],
                "repair_transition": {
                    "schema_version": REPAIR_SCHEMA_VERSION,
                    "repair_id": self.repair_id,
                    "kind": self.kind.value,
                    "source_conflict_ids": list(self.source_conflict_ids),
                    "supersede_constraint_ids": list(
                        self.supersede_constraint_ids
                    ),
                    "risk": self.risk.value,
                },
            },
        )

    def verification_action(self) -> ActionSpec:
        return ActionSpec(
            action_type="verification",
            command=self.probe.command,
            rationale=f"Verify typed repair {self.repair_id}",
            action_id=self.verification_action_id,
            metadata={
                "mutates_environment": False,
                "repair_id": self.repair_id,
                "probe": self.probe.to_dict(),
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.semantic_dict(),
            "repair_id": self.repair_id,
            "rationale": self.rationale,
            "mutation_action_id": self.mutation_action_id,
            "verification_action_id": self.verification_action_id,
        }
