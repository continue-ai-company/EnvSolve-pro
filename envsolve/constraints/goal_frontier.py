from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import PurePosixPath
from typing import Any

from envsolve.state import EnvironmentState


GOAL_OBLIGATION_FRONTIER_SCHEMA = "envsolve-goal-obligation-frontier-v1"
MODEL_GOAL_OBLIGATION_FRONTIER_SCHEMA = (
    "envsolve-model-goal-obligation-frontier-v1"
)

_GENERATED_COMPONENTS = frozenset(
    {"build", "dist", "site-packages", "__pycache__"}
)
_TEST_COMPONENTS = frozenset({"test", "tests"})
_DOC_COMPONENTS = frozenset({"doc", "docs"})
_EXAMPLE_COMPONENTS = frozenset({"demo", "demos", "example", "examples"})
_ROLE_PRIORITY = {
    "runtime": 0,
    "test": 1,
    "docs": 2,
    "example": 3,
    "generated": 4,
    "unknown": 5,
}


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _json_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=True, sort_keys=True))


def _root_id(value: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
    return f"goal-root-{digest[:20]}"


def _goal_report(
    state: EnvironmentState,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    for verification in reversed(state.verifications):
        details = verification.get("details")
        if not isinstance(details, dict):
            continue
        diagnostic = details.get("verifier_details", details)
        if not isinstance(diagnostic, dict):
            continue
        report_details = diagnostic.get("report_details", diagnostic)
        if not isinstance(report_details, dict):
            continue
        report = report_details.get("goal_report")
        if (
            isinstance(report, dict)
            and isinstance(report.get("findings"), list)
        ):
            return verification, report
    return None


def _path_parts(path: object) -> tuple[str, ...]:
    if not isinstance(path, str) or not path.strip():
        return ()
    return tuple(part.lower() for part in PurePosixPath(path).parts)


def source_role(path: object) -> str:
    """Classify where a goal finding occurs without changing its obligation."""
    parts = _path_parts(path)
    if not parts:
        return "unknown"
    if any(part in _GENERATED_COMPONENTS for part in parts):
        return "generated"
    if any(part in _TEST_COMPONENTS for part in parts):
        return "test"
    if any(part in _DOC_COMPONENTS for part in parts):
        return "docs"
    if any(part in _EXAMPLE_COMPONENTS for part in parts):
        return "example"
    return "runtime"


def _display_path(path: object) -> str | None:
    if not isinstance(path, str) or not path.strip():
        return None
    marker = "/data/project/"
    if path.startswith(marker):
        remainder = path[len(marker) :]
        _, separator, relative = remainder.partition("/")
        if separator and relative:
            return relative
    return PurePosixPath(path).as_posix()


def _canonical_source_path(path: object) -> str | None:
    display = _display_path(path)
    if display is None:
        return None
    parts = PurePosixPath(display).parts
    if len(parts) >= 3 and parts[0].lower() == "build":
        if parts[1].lower() in {"lib", "src"}:
            return PurePosixPath(*parts[2:]).as_posix()
    return display


def _active_finding(finding: dict[str, Any]) -> bool:
    observed = finding.get("observed")
    return observed is not None and observed != finding.get("required")


def _group_key(finding: dict[str, Any]) -> tuple[str, str, str, str]:
    domain = str(finding.get("domain", "unknown"))
    subject = str(finding.get("subject", "unknown"))
    root_subject = (
        subject.split(".", 1)[0]
        if domain == "module" and subject
        else subject
    )
    return (
        domain,
        root_subject,
        str(finding.get("predicate", "unknown")),
        _canonical_json(finding.get("required")),
    )


def _finding_path(finding: dict[str, Any]) -> object:
    provenance = finding.get("provenance")
    return provenance.get("file") if isinstance(provenance, dict) else None


def _group_priority(group: dict[str, Any]) -> tuple[int, int, int, str]:
    roles = group["source_roles"]
    role_rank = min(
        (_ROLE_PRIORITY.get(str(role), 99) for role in roles),
        default=99,
    )
    return (
        0 if group["domain"] != "module" else 1,
        role_rank,
        -int(group["surface_finding_count"]),
        str(group["subject"]),
    )


def _build_groups(
    findings: tuple[dict[str, Any], ...],
) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str, str], list[dict[str, Any]]]]:
    grouped_findings: dict[
        tuple[str, str, str, str], list[dict[str, Any]]
    ] = {}
    for finding in findings:
        grouped_findings.setdefault(_group_key(finding), []).append(finding)

    groups: list[dict[str, Any]] = []
    for key, members in grouped_findings.items():
        domain, subject, predicate, encoded_required = key
        roles = Counter(source_role(_finding_path(item)) for item in members)
        subjects = sorted(
            {
                str(item.get("subject"))
                for item in members
                if isinstance(item.get("subject"), str)
            }
        )
        paths = sorted(
            {
                display
                for item in members
                if (display := _display_path(_finding_path(item))) is not None
            },
            key=lambda path: (
                _ROLE_PRIORITY[source_role(path)],
                path,
            ),
        )
        canonical_occurrences = {
            (
                str(item.get("subject")),
                _canonical_source_path(_finding_path(item)),
            )
            for item in members
        }
        semantic = {
            "domain": domain,
            "subject": subject,
            "predicate": predicate,
            "required": json.loads(encoded_required),
        }
        finding_ids = sorted(
            {
                str(item["finding_id"])
                for item in members
                if isinstance(item.get("finding_id"), str)
            }
        )
        groups.append(
            {
                "root_id": _root_id(semantic),
                "root_kind": (
                    "unresolved_module_namespace"
                    if domain == "module"
                    else "unresolved_goal_obligation"
                ),
                **semantic,
                "goal_obligation": True,
                "aggregation_basis": (
                    "shared_top_level_import_namespace"
                    if domain == "module"
                    else "shared_goal_predicate"
                ),
                "action_mapping_grounded": False,
                "surface_finding_count": len(members),
                "distinct_surface_subject_count": len(subjects),
                "surface_subjects": subjects,
                "source_roles": dict(sorted(roles.items())),
                "source_file_count": len(paths),
                "source_files": paths,
                "canonical_source_occurrence_count": len(
                    canonical_occurrences
                ),
                "duplicate_surface_occurrence_count": (
                    len(members) - len(canonical_occurrences)
                ),
                "finding_ids": finding_ids,
            }
        )
    groups.sort(key=_group_priority)
    return groups, grouped_findings


def ordered_active_goal_findings(
    state: EnvironmentState,
) -> tuple[dict[str, Any], ...]:
    """Return one evidence-routing representative per obligation group."""
    current = _goal_report(state)
    if current is None:
        return ()
    _, report = current
    active = tuple(
        item
        for item in report["findings"]
        if isinstance(item, dict) and _active_finding(item)
    )
    groups, grouped_findings = _build_groups(active)
    representatives: list[dict[str, Any]] = []
    for group in groups:
        key = (
            str(group["domain"]),
            str(group["subject"]),
            str(group["predicate"]),
            _canonical_json(group["required"]),
        )
        members = grouped_findings[key]
        representatives.append(
            min(
                members,
                key=lambda item: (
                    _ROLE_PRIORITY[source_role(_finding_path(item))],
                    str(_display_path(_finding_path(item))),
                    str(item.get("subject", "")),
                    str(item.get("finding_id", "")),
                ),
            )
        )
    return tuple(representatives)


def build_goal_obligation_frontier(
    state: EnvironmentState,
) -> dict[str, Any]:
    """Compress complete goal findings without guessing package actions."""
    current = _goal_report(state)
    if current is None:
        return {
            "schema": GOAL_OBLIGATION_FRONTIER_SCHEMA,
            "source_verification_id": None,
            "source_candidate_id": None,
            "finding_set_complete": False,
            "raw_findings_retained": True,
            "hard_state_mutated": False,
            "obligation_groups": [],
            "summary": {
                "active_finding_count": 0,
                "unknown_finding_count": 0,
                "obligation_group_count": 0,
                "compression_ratio": None,
            },
        }
    verification, report = current
    findings = tuple(
        item for item in report["findings"] if isinstance(item, dict)
    )
    active = tuple(item for item in findings if _active_finding(item))
    unknown_count = sum(
        1 for item in findings if item.get("observed") is None
    )
    groups, _ = _build_groups(active)
    details = verification.get("details")
    candidate_id = (
        details.get("candidate_id")
        if isinstance(details, dict)
        else None
    )
    return {
        "schema": GOAL_OBLIGATION_FRONTIER_SCHEMA,
        "source_verification_id": verification.get("verification_id"),
        "source_candidate_id": candidate_id,
        "finding_set_complete": report.get("finding_set_complete") is True,
        "raw_findings_retained": True,
        "hard_state_mutated": False,
        "obligation_groups": groups,
        "summary": {
            "active_finding_count": len(active),
            "unknown_finding_count": unknown_count,
            "obligation_group_count": len(groups),
            "compression_ratio": (
                round(len(active) / len(groups), 3) if groups else None
            ),
        },
    }


def _model_group(group: dict[str, Any]) -> dict[str, Any]:
    value = {
        key: group[key]
        for key in (
            "root_id",
            "domain",
            "subject",
            "surface_finding_count",
            "distinct_surface_subject_count",
            "source_roles",
        )
    } | {
        "surface_subjects_sample": group["surface_subjects"][:4],
        "source_files_sample": group["source_files"][:2],
    }
    if group["predicate"] != "present" or group["required"] is not True:
        value["predicate"] = group["predicate"]
        value["required"] = group["required"]
    if group["duplicate_surface_occurrence_count"]:
        value["duplicate_surface_occurrence_count"] = group[
            "duplicate_surface_occurrence_count"
        ]
    return value


def build_model_goal_obligation_frontier(
    state: EnvironmentState,
    *,
    max_chars: int = 12_000,
) -> dict[str, Any]:
    """Build a bounded structured view for model inference."""
    if max_chars < 512:
        raise ValueError(
            "Model goal-obligation frontier budget must be at least 512 characters"
        )
    full = build_goal_obligation_frontier(state)
    groups = full["obligation_groups"]
    projection = {
        "schema": full["schema"],
        "model_projection_schema": MODEL_GOAL_OBLIGATION_FRONTIER_SCHEMA,
        "source_verification_id": full["source_verification_id"],
        "source_candidate_id": full["source_candidate_id"],
        "finding_set_complete": full["finding_set_complete"],
        "raw_findings_retained": True,
        "raw_findings_included": False,
        "hard_state_mutated": False,
        "group_semantics": {
            "all_groups_are_goal_obligations": True,
            "source_roles_do_not_waive_obligations": True,
            "module_aggregation_basis": (
                "shared_top_level_import_namespace"
            ),
            "action_mapping_grounded": False,
        },
        "obligation_groups": [],
        "summary": {
            **full["summary"],
            "obligation_groups_included": 0,
            "obligation_groups_omitted": len(groups),
            "projection_complete": not groups,
        },
    }
    if _json_size(projection) > max_chars:
        raise ValueError(
            "Model goal-obligation frontier budget cannot encode its skeleton"
        )
    for group in groups:
        projection["obligation_groups"].append(_model_group(group))
        included = len(projection["obligation_groups"])
        projection["summary"]["obligation_groups_included"] = included
        projection["summary"]["obligation_groups_omitted"] = (
            len(groups) - included
        )
        projection["summary"]["projection_complete"] = included == len(groups)
        if _json_size(projection) > max_chars:
            projection["obligation_groups"].pop()
            included -= 1
            projection["summary"]["obligation_groups_included"] = included
            projection["summary"]["obligation_groups_omitted"] = (
                len(groups) - included
            )
            projection["summary"]["projection_complete"] = False
            break
    return projection
