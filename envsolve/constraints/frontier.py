from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from typing import Any, Iterable

from packaging.version import InvalidVersion, Version

from envsolve.analysis.runtime_compatibility import parse_runtime_compatibility
from envsolve.constraints.engine import ConstraintEngine
from envsolve.constraints.models import (
    ConstraintDomain,
    ConstraintPredicate,
    ConstraintRole,
    NormalizedConstraint,
)
from envsolve.state import EnvironmentState


FRONTIER_SCHEMA_VERSION = "1.1.0"
MODEL_FRONTIER_SCHEMA_VERSION = "1.0.0"


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _node_id(value: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()[:20]
    return f"frontier-{digest}"


def _event_sequence(record: dict[str, Any]) -> int:
    metadata = record.get("state_metadata")
    value = metadata.get("event_sequence") if isinstance(metadata, dict) else None
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else -1


def _record_scope_id(record: dict[str, Any]) -> str | None:
    candidate_id = record.get("candidate_id")
    if isinstance(candidate_id, str) and candidate_id.strip():
        return candidate_id.strip()
    value = record.get("value")
    action_id = value.get("action_id") if isinstance(value, dict) else None
    if isinstance(action_id, str) and action_id.strip():
        return action_id.strip()
    return None


def _latest_execution_scope(state: EnvironmentState) -> str | None:
    candidates = [
        (str(action_id), _event_sequence(action))
        for action_id, action in state.actions.items()
        if isinstance(action_id, str) and action_id.strip()
    ]
    if candidates:
        return max(candidates, key=lambda item: (item[1], item[0]))[0]
    evidence_candidates = [
        (scope_id, _event_sequence(record), evidence_id)
        for evidence_id, record in state.evidence.items()
        if (scope_id := _record_scope_id(record)) is not None
    ]
    if not evidence_candidates:
        return None
    return max(evidence_candidates, key=lambda item: (item[1], item[2]))[0]


def _trust_level(record: dict[str, Any]) -> str:
    source = str(record.get("source", ""))
    if source.startswith("repository-declaration:"):
        return "repository_declaration"
    if source.startswith("fresh-base-runtime:"):
        return "fresh_environment"
    if source.startswith("executable-verifier:") or source in {
        "fresh-environment-replay",
        "recorded-action",
    }:
        return "fresh_execution"
    return "unclassified"


def _source_roles(provenance: dict[str, Any]) -> tuple[str, ...]:
    evidence = provenance.get("evidence")
    if not isinstance(evidence, list):
        return ()
    return tuple(
        str(item["detail"])
        for item in evidence
        if isinstance(item, dict)
        and item.get("kind") == "source-role"
        and isinstance(item.get("detail"), str)
    )


def _module_obligation_records(
    state: EnvironmentState,
    constraint: NormalizedConstraint,
) -> tuple[tuple[str, dict[str, Any], str, dict[str, Any]], ...]:
    records: list[tuple[str, dict[str, Any], str, dict[str, Any]]] = []
    for evidence_id in constraint.evidence_ids:
        record = state.evidence.get(evidence_id)
        if not isinstance(record, dict) or record.get("kind") != "module-requirement":
            continue
        value = record.get("value")
        provenance = value.get("finding_provenance") if isinstance(value, dict) else None
        runtime = provenance.get("runtime_observation") if isinstance(provenance, dict) else None
        missing_name = runtime.get("missing_name") if isinstance(runtime, dict) else None
        if (
            not isinstance(missing_name, str)
            or not missing_name.strip()
            or runtime.get("status") != "missing"
        ):
            continue
        records.append((evidence_id, record, missing_name.strip(), provenance))
    return tuple(records)


def _latest_module_observation_scope(
    state: EnvironmentState,
    fallback_values: Iterable[
        tuple[str, dict[str, Any], str, dict[str, Any]]
    ],
) -> str | None:
    candidates = [
        (scope_id, _event_sequence(record), evidence_id)
        for evidence_id, record in state.evidence.items()
        if record.get("kind") in {"module-observation", "module-requirement"}
        and (scope_id := _record_scope_id(record)) is not None
    ]
    if not candidates:
        candidates = [
            (scope_id, _event_sequence(record), evidence_id)
            for evidence_id, record, _, _ in fallback_values
            if (scope_id := _record_scope_id(record)) is not None
        ]
    if not candidates:
        return None
    return str(max(candidates, key=lambda item: (item[1], item[2]))[0])


def _module_roots(
    state: EnvironmentState,
    constraints: tuple[NormalizedConstraint, ...],
    hard_confidence: float,
) -> tuple[list[dict[str, Any]], set[str], int, list[str], str | None]:
    obligations = [
        item
        for item in constraints
        if item.domain is ConstraintDomain.MODULE
        and item.role is ConstraintRole.REQUIREMENT
        and item.predicate is ConstraintPredicate.PRESENT
        and item.value is True
        and item.confidence >= hard_confidence
        and state.constraints[item.constraint_id].get("status") in {"active", "violated"}
    ]
    causal_records = {
        item.constraint_id: _module_obligation_records(state, item)
        for item in obligations
    }
    current_scope = _latest_module_observation_scope(
        state,
        (record for records in causal_records.values() for record in records),
    )
    groups: dict[tuple[str, str | None], dict[str, Any]] = defaultdict(
        lambda: {
            "constraint_ids": set(),
            "evidence_ids": set(),
            "paths": set(),
            "roles": Counter(),
            "surface_subjects": set(),
            "occurrences": 0,
        }
    )
    grouped_constraint_ids: set[str] = set()
    for constraint in obligations:
        records = causal_records[constraint.constraint_id]
        if current_scope is not None:
            records = tuple(
                item for item in records if item[1].get("candidate_id") == current_scope
            )
        for evidence_id, record, missing_name, provenance in records:
            scope_id = record.get("candidate_id")
            key = (missing_name, str(scope_id) if scope_id is not None else None)
            group = groups[key]
            group["constraint_ids"].add(constraint.constraint_id)
            group["evidence_ids"].add(evidence_id)
            group["surface_subjects"].add(constraint.subject)
            group["occurrences"] += 1
            path = provenance.get("path")
            if isinstance(path, str) and path:
                group["paths"].add(path)
            group["roles"].update(_source_roles(provenance))
            grouped_constraint_ids.add(constraint.constraint_id)

    roots: list[dict[str, Any]] = []
    for (missing_name, scope_id), group in sorted(groups.items()):
        semantic = {
            "root_kind": "runtime_missing_dependency",
            "domain": "module",
            "subject": missing_name,
        }
        subjects = sorted(group["surface_subjects"])
        evidence_ids = sorted(group["evidence_ids"])
        paths = sorted(group["paths"])
        roots.append(
            {
                "root_id": _node_id(semantic),
                **semantic,
                "scope_id": scope_id,
                "causal_relation": "surface_import_failed_on_runtime_missing_name",
                "trust_level": "fresh_execution",
                "hard_constraint": False,
                "occurrence_count": int(group["occurrences"]),
                "surface_constraint_count": len(group["constraint_ids"]),
                "surface_subject_count": len(subjects),
                "surface_subjects": subjects[:20],
                "surface_subjects_truncated": len(subjects) > 20,
                "source_roles": dict(sorted(group["roles"].items())),
                "source_paths": paths[:20],
                "source_paths_truncated": len(paths) > 20,
                "evidence_ids": evidence_ids[:20],
                "evidence_count": len(evidence_ids),
            }
        )
    ungrouped = sorted(
        item.subject
        for item in obligations
        if item.constraint_id not in grouped_constraint_ids
    )
    return roots, grouped_constraint_ids, len(obligations), ungrouped, current_scope


def _verified_runtime_facts(
    state: EnvironmentState,
) -> list[tuple[int, dict[str, Any]]]:
    values: list[tuple[int, dict[str, Any]]] = []
    for verification in state.verifications:
        details = verification.get("details")
        verifier_details = (
            details.get("verifier_details") if isinstance(details, dict) else None
        )
        report_details = (
            verifier_details.get("report_details")
            if isinstance(verifier_details, dict)
            else None
        )
        facts = (
            report_details.get("environment_facts")
            if isinstance(report_details, dict)
            else None
        )
        if not isinstance(facts, dict):
            continue
        values.append(
            (
                _event_sequence(verification),
                facts,
            )
        )
    return values


def _runtime_version_within_maximum(observed: str, maximum: str) -> bool:
    try:
        observed_release = Version(observed).release
        maximum_release = Version(maximum).release
    except InvalidVersion:
        return False
    width = len(maximum_release)
    return observed_release[:width] <= maximum_release


def _runtime_roots(state: EnvironmentState) -> list[dict[str, Any]]:
    roots: dict[str, dict[str, Any]] = {}
    for evidence_id, record in sorted(state.evidence.items()):
        scope_id = _record_scope_id(record)
        value = record.get("value")
        findings = ()
        if record.get("kind") == "runtime-compatibility-observation" and isinstance(
            value, dict
        ):
            if all(
                isinstance(value.get(key), str)
                for key in (
                    "provider",
                    "runtime",
                    "observed_version",
                    "maximum_supported_version",
                    "signature",
                )
            ):
                findings = (value,)
        elif (
            record.get("kind") == "action-result"
            and isinstance(value, dict)
            and value.get("exit_code") != 0
        ):
            text = f"{value.get('stdout', '')}\n{value.get('stderr', '')}"
            findings = tuple(item.to_dict() for item in parse_runtime_compatibility(text))
        for finding in findings:
            semantic = {
                "root_kind": "runtime_compatibility_frontier",
                "domain": "runtime",
                "subject": finding["runtime"],
                "provider": finding["provider"],
                "observed_version": finding["observed_version"],
                "maximum_supported_version": finding[
                    "maximum_supported_version"
                ],
            }
            node_id = _node_id(semantic)
            root = roots.setdefault(
                node_id,
                {
                    "root_id": node_id,
                    **semantic,
                    "causal_relation": "provider_rejected_observed_runtime",
                    "signature": finding["signature"],
                    "trust_levels": set(),
                    "hard_constraint": False,
                    "evidence_ids": [],
                    "observed_scopes": set(),
                    "last_observed_sequence": -1,
                    "last_observed_scope": None,
                },
            )
            root["trust_levels"].add(_trust_level(record))
            root["evidence_ids"].append(evidence_id)
            if scope_id is not None:
                root["observed_scopes"].add(scope_id)
            sequence = _event_sequence(record)
            if sequence >= int(root["last_observed_sequence"]):
                root["last_observed_sequence"] = sequence
                root["last_observed_scope"] = scope_id
    verified_facts = _verified_runtime_facts(state)
    values: list[dict[str, Any]] = []
    for key in sorted(roots):
        root = roots[key]
        resolved = any(
            sequence > int(root["last_observed_sequence"])
            and root["subject"] == "python"
            and isinstance(facts.get("python_version"), str)
            and _runtime_version_within_maximum(
                str(facts["python_version"]),
                str(root["maximum_supported_version"]),
            )
            for sequence, facts in verified_facts
        )
        if resolved:
            continue
        root["trust_levels"] = sorted(root["trust_levels"])
        root["evidence_ids"] = sorted(set(root["evidence_ids"]))
        root["evidence_count"] = len(root["evidence_ids"])
        root["observed_scopes"] = sorted(root["observed_scopes"])
        root["scope_id"] = root.pop("last_observed_scope")
        root["resolution_requirement"] = (
            "newer fresh verifier observation within the supported runtime frontier"
        )
        values.append(root)
    return values


def _environment_facts(
    state: EnvironmentState,
    constraints: tuple[NormalizedConstraint, ...],
    hard_confidence: float,
) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for item in constraints:
        if (
            item.role is not ConstraintRole.FACT
            or item.domain not in {ConstraintDomain.RUNTIME, ConstraintDomain.PLATFORM}
            or item.confidence < hard_confidence
        ):
            continue
        evidence = [
            state.evidence[evidence_id]
            for evidence_id in item.evidence_ids
            if evidence_id in state.evidence
        ]
        trust_levels = sorted({_trust_level(record) for record in evidence})
        values.append(
            {
                "constraint_id": item.constraint_id,
                "domain": item.domain.value,
                "subject": item.subject,
                "predicate": item.predicate.value,
                "observed": item.value,
                "scope_id": item.scope_id,
                "trust_levels": trust_levels,
                "evidence_ids": list(item.evidence_ids),
            }
        )
    return sorted(
        values,
        key=lambda item: (
            str(item["domain"]),
            str(item["subject"]),
            str(item["scope_id"]),
            str(item["constraint_id"]),
        ),
    )


def build_causal_constraint_frontier(
    state: EnvironmentState,
    engine: ConstraintEngine | None = None,
) -> dict[str, Any]:
    """Derive prioritized roots without mutating or discarding raw solver state."""
    constraint_engine = engine or ConstraintEngine()
    constraints = constraint_engine.typed_constraints(state)
    latest_execution_scope = _latest_execution_scope(state)
    (
        module_roots,
        grouped_ids,
        surface_count,
        ungrouped,
        module_observation_scope,
    ) = _module_roots(
        state,
        constraints,
        constraint_engine.hard_confidence,
    )
    roots = sorted(
        [*module_roots, *_runtime_roots(state)],
        key=lambda item: str(item["root_id"]),
    )
    return {
        "schema_version": FRONTIER_SCHEMA_VERSION,
        "raw_evidence_retained": True,
        "hard_state_mutated": False,
        "latest_execution_scope": latest_execution_scope,
        "latest_module_observation_scope": module_observation_scope,
        "observed_environment_facts": _environment_facts(
            state,
            constraints,
            constraint_engine.hard_confidence,
        ),
        "causal_roots": roots,
        "summary": {
            "causal_root_count": len(roots),
            "surface_module_obligation_count": surface_count,
            "causally_grouped_surface_constraint_count": len(grouped_ids),
            "ungrouped_surface_constraint_count": surface_count - len(grouped_ids),
            "maximum_surface_amplification": max(
                (
                    int(root.get("surface_constraint_count", 0))
                    for root in module_roots
                ),
                default=0,
            ),
            "ungrouped_surface_subjects": ungrouped[:20],
            "ungrouped_surface_subjects_truncated": len(ungrouped) > 20,
        },
    }


def _model_value(value: Any, limit: int = 256) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_model_value(item, 64) for item in value[:8]]
    if isinstance(value, dict):
        return {
            str(key)[:64]: _model_value(item, 64)
            for key, item in list(value.items())[:8]
        }
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _model_root(root: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "root_id",
        "root_kind",
        "domain",
        "subject",
        "provider",
        "observed_version",
        "maximum_supported_version",
        "scope_id",
        "causal_relation",
        "hard_constraint",
        "trust_level",
        "trust_levels",
        "evidence_count",
        "occurrence_count",
        "surface_constraint_count",
        "surface_subject_count",
        "source_roles",
        "resolution_requirement",
    )
    value = {key: _model_value(root[key]) for key in fields if key in root}
    surfaces = root.get("surface_subjects")
    if isinstance(surfaces, list):
        value["surface_subjects_sample"] = [
            _model_value(item) for item in surfaces[:3]
        ]
    return value


def _root_priority(root: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        0 if root.get("root_kind") == "runtime_compatibility_frontier" else 1,
        -int(root.get("surface_constraint_count", 0)),
        -int(root.get("evidence_count", 0)),
        str(root.get("root_id", "")),
    )


def build_model_constraint_frontier(
    state: EnvironmentState,
    engine: ConstraintEngine | None = None,
    *,
    max_chars: int = 9_000,
) -> dict[str, Any]:
    """Project the full frontier into a bounded, always-structured model view."""
    if max_chars < 128:
        raise ValueError("Model frontier budget must be at least 128 characters")
    full = build_causal_constraint_frontier(state, engine)
    all_facts = [
        {
            key: _model_value(item[key])
            for key in (
                "domain",
                "subject",
                "predicate",
                "observed",
                "scope_id",
                "trust_levels",
            )
            if key in item
        }
        for item in full["observed_environment_facts"]
    ]
    roots = sorted(full["causal_roots"], key=_root_priority)
    projection = {
        "schema_version": full["schema_version"],
        "model_projection_schema_version": MODEL_FRONTIER_SCHEMA_VERSION,
        "raw_evidence_retained": True,
        "hard_state_mutated": False,
        "latest_execution_scope": full["latest_execution_scope"],
        "latest_module_observation_scope": full[
            "latest_module_observation_scope"
        ],
        "observed_environment_facts": [],
        "causal_roots": [],
        "summary": {
            key: full["summary"][key]
            for key in (
                "causal_root_count",
                "surface_module_obligation_count",
                "causally_grouped_surface_constraint_count",
                "ungrouped_surface_constraint_count",
                "maximum_surface_amplification",
            )
        } | {
            "environment_fact_count": len(all_facts),
            "environment_facts_included": 0,
            "environment_facts_omitted": len(all_facts),
            "causal_roots_included": 0,
            "causal_roots_omitted": len(roots),
            "projection_complete": not roots,
        },
    }
    if len(json.dumps(projection, ensure_ascii=True, sort_keys=True)) > max_chars:
        projection = {
            "causal_roots": [],
            "summary": {
                "causal_root_count": len(roots),
                "causal_roots_omitted": len(roots),
                "projection_complete": not roots and not all_facts,
            },
        }
        if len(json.dumps(projection, ensure_ascii=True, sort_keys=True)) > max_chars:
            raise ValueError("Model frontier budget cannot encode its structured skeleton")
        return projection
    for root in roots:
        compact = _model_root(root)
        projection["causal_roots"].append(compact)
        included = len(projection["causal_roots"])
        projection["summary"]["causal_roots_included"] = included
        projection["summary"]["causal_roots_omitted"] = len(roots) - included
        projection["summary"]["projection_complete"] = (
            included == len(roots)
            and projection["summary"]["environment_facts_omitted"] == 0
        )
        if len(json.dumps(projection, ensure_ascii=True, sort_keys=True)) > max_chars:
            projection["causal_roots"].pop()
            included -= 1
            projection["summary"]["causal_roots_included"] = included
            projection["summary"]["causal_roots_omitted"] = len(roots) - included
            projection["summary"]["projection_complete"] = False
            break
    for fact in all_facts:
        projection["observed_environment_facts"].append(fact)
        included = len(projection["observed_environment_facts"])
        projection["summary"]["environment_facts_included"] = included
        projection["summary"]["environment_facts_omitted"] = len(all_facts) - included
        projection["summary"]["projection_complete"] = (
            included == len(all_facts)
            and projection["summary"]["causal_roots_omitted"] == 0
        )
        if len(json.dumps(projection, ensure_ascii=True, sort_keys=True)) > max_chars:
            projection["observed_environment_facts"].pop()
            included -= 1
            projection["summary"]["environment_facts_included"] = included
            projection["summary"]["environment_facts_omitted"] = (
                len(all_facts) - included
            )
            projection["summary"]["projection_complete"] = False
            break
    if len(json.dumps(projection, ensure_ascii=True, sort_keys=True)) > max_chars:
        raise ValueError("Model frontier metadata exceeds its structured budget")
    return projection
