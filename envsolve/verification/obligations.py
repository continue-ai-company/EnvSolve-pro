from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from envsolve.verification.imports import ImportAssessment, ImportDisposition


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    MISSING = "missing"
    UNKNOWN = "unknown"


class ObligationLayer(str, Enum):
    RUNTIME_SEMANTIC = "runtime_semantic"
    STATIC_SOURCE = "static_source"


class ObligationDisposition(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ImportObligationDecision:
    disposition: ObligationDisposition
    active_layers: tuple[ObligationLayer, ...]
    unknown_layers: tuple[ObligationLayer, ...]
    required_layers: tuple[ObligationLayer, ...]


def decide_import_obligation(
    assessment: ImportAssessment,
    runtime_status: ResolutionStatus,
    static_status: ResolutionStatus,
    *,
    fallback_modules: tuple[str, ...] = (),
    runtime_statuses: Mapping[str, ResolutionStatus] | None = None,
    static_layer_enabled: bool = True,
) -> ImportObligationDecision:
    """Combine independent runtime and static evidence for one source import."""
    runtime_required = assessment.disposition in {
        ImportDisposition.ACTIVE_OBLIGATION,
        ImportDisposition.UNRESOLVED,
    }
    static_required = static_layer_enabled and assessment.disposition not in {
        ImportDisposition.INACTIVE_PLATFORM,
        ImportDisposition.PROJECT_EXCLUDED_FIXTURE,
        ImportDisposition.DOCUMENTATION_SCOPE,
    }
    if assessment.disposition is ImportDisposition.STATIC_ONLY:
        runtime_required = False

    required: list[ObligationLayer] = []
    active: list[ObligationLayer] = []
    unknown: list[ObligationLayer] = []

    if runtime_required:
        required.append(ObligationLayer.RUNTIME_SEMANTIC)
        if runtime_status is ResolutionStatus.MISSING:
            alternatives = tuple(
                (runtime_statuses or {}).get(name) for name in fallback_modules
            )
            if fallback_modules and ResolutionStatus.RESOLVED in alternatives:
                pass
            elif fallback_modules:
                unknown.append(ObligationLayer.RUNTIME_SEMANTIC)
            else:
                active.append(ObligationLayer.RUNTIME_SEMANTIC)
        elif runtime_status is ResolutionStatus.UNKNOWN:
            unknown.append(ObligationLayer.RUNTIME_SEMANTIC)

    if static_required:
        required.append(ObligationLayer.STATIC_SOURCE)
        if static_status is ResolutionStatus.MISSING:
            active.append(ObligationLayer.STATIC_SOURCE)
        elif static_status is ResolutionStatus.UNKNOWN:
            unknown.append(ObligationLayer.STATIC_SOURCE)

    disposition = (
        ObligationDisposition.ACTIVE
        if active
        else ObligationDisposition.UNKNOWN
        if unknown
        else ObligationDisposition.INACTIVE
    )
    return ImportObligationDecision(
        disposition,
        tuple(active),
        tuple(unknown),
        tuple(required),
    )
