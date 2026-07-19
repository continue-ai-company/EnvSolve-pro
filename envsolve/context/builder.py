from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from envsolve.context.models import (
    SYSTEM_MANAGER_PRIORITY,
    ParsedContextEvidence,
    parse_context_evidence,
)
from envsolve.repairs import RepairContext
from envsolve.state import EnvironmentState


@dataclass(frozen=True)
class ContextBuildReport:
    context: RepairContext
    recognized_evidence_ids: tuple[str, ...]
    provisional_evidence_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "context": self.context.to_dict(),
            "recognized_evidence_ids": list(self.recognized_evidence_ids),
            "provisional_evidence_ids": list(self.provisional_evidence_ids),
        }


def _presence(
    values: list[ParsedContextEvidence],
    name_field: str,
) -> dict[str, tuple[bool, str]]:
    grouped: dict[str, list[ParsedContextEvidence]] = {}
    for item in values:
        grouped.setdefault(str(item.value[name_field]), []).append(item)
    result: dict[str, tuple[bool, str]] = {}
    for name, evidence in grouped.items():
        current = max(evidence, key=lambda item: (item.event_sequence, item.evidence_id))
        result[name] = (bool(current.value["present"]), current.evidence_id)
    return result


def _latest(
    values: list[ParsedContextEvidence],
    *key_fields: str,
) -> tuple[ParsedContextEvidence, ...]:
    selected: dict[tuple[str, ...], ParsedContextEvidence] = {}
    for item in values:
        key = tuple(str(item.value[field]) for field in key_fields)
        previous = selected.get(key)
        if previous is None or (item.event_sequence, item.evidence_id) > (
            previous.event_sequence,
            previous.evidence_id,
        ):
            selected[key] = item
    return tuple(selected[key] for key in sorted(selected))


def build_repair_context(
    state: EnvironmentState,
    hard_confidence: float = 0.8,
) -> ContextBuildReport:
    if isinstance(hard_confidence, bool) or not 0 <= hard_confidence <= 1:
        raise ValueError("hard_confidence must be in [0, 1]")
    recognized: list[ParsedContextEvidence] = []
    provisional: list[str] = []
    for evidence_id, record in sorted(state.evidence.items()):
        parsed = parse_context_evidence(evidence_id, record)
        if parsed is None:
            continue
        if parsed.confidence < hard_confidence:
            provisional.append(evidence_id)
            continue
        recognized.append(parsed)

    tools = _presence(
        [item for item in recognized if item.kind == "context-tool-observation"],
        "tool",
    )
    managers = _presence(
        [
            item
            for item in recognized
            if item.kind == "context-system-manager-observation"
        ],
        "manager",
    )
    selected_evidence: set[str] = set()
    runtime_manager: str | None = None
    runtime_root: str | None = None
    versions: set[str] = set()
    pyenv = tools.get("pyenv")
    if pyenv is not None and pyenv[0]:
        runtime_manager = "pyenv"
        selected_evidence.add(pyenv[1])
        roots = _latest(
            [item for item in recognized if item.kind == "context-runtime-root"],
            "manager",
        )
        for item in roots:
            if item.value["manager"] == "pyenv":
                runtime_root = str(item.value["root"])
                selected_evidence.add(item.evidence_id)
        inventories = _latest(
            [item for item in recognized if item.kind == "context-runtime-inventory"],
            "manager",
        )
        for item in inventories:
            if (
                item.kind == "context-runtime-inventory"
                and item.value["manager"] == "pyenv"
            ):
                versions.update(str(value) for value in item.value["versions"])
                selected_evidence.add(item.evidence_id)

    system_manager = next(
        (
            manager
            for manager in SYSTEM_MANAGER_PRIORITY
            if managers.get(manager, (False, ""))[0]
        ),
        None,
    )
    if system_manager is not None:
        selected_evidence.add(managers[system_manager][1])

    capability_packages: dict[str, set[str]] = {}
    module_distributions: dict[str, set[str]] = {}
    candidates = _latest(
        [
            item
            for item in recognized
            if item.kind == "context-capability-package-candidate"
        ],
        "capability",
        "manager",
    )
    module_candidates = _latest(
        [
            item
            for item in recognized
            if item.kind == "context-module-distribution-candidate"
        ],
        "module",
    )
    for item in (*candidates, *module_candidates):
        if (
            item.kind == "context-capability-package-candidate"
            and item.value["manager"] == system_manager
        ):
            capability_packages.setdefault(
                str(item.value["capability"]), set()
            ).update(str(value) for value in item.value["packages"])
            selected_evidence.add(item.evidence_id)
        elif item.kind == "context-module-distribution-candidate":
            module_distributions.setdefault(
                str(item.value["module"]), set()
            ).update(str(value) for value in item.value["distributions"])
            selected_evidence.add(item.evidence_id)

    context = RepairContext(
        runtime_manager=runtime_manager,
        runtime_root=runtime_root,
        available_python_versions=tuple(versions),
        system_package_manager=system_manager,
        capability_packages={
            name: tuple(values) for name, values in capability_packages.items()
        },
        module_distributions={
            name: tuple(values) for name, values in module_distributions.items()
        },
        evidence_ids=tuple(selected_evidence),
    )
    return ContextBuildReport(
        context=context,
        recognized_evidence_ids=tuple(item.evidence_id for item in recognized),
        provisional_evidence_ids=tuple(sorted(provisional)),
    )
