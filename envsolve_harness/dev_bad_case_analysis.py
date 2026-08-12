from __future__ import annotations

from collections import defaultdict
import hashlib
from typing import Any, Iterable, Mapping, Sequence


CORE_BATCH_SALT = "envsolve-pro-core-batch-v1-2026-08-09"


def _require_string(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Classification requires non-empty {key!r}")
    return value


def _failure_subtypes(taxonomy: Mapping[str, Any]) -> dict[str, set[str]]:
    layers = taxonomy.get("failure_layers")
    if not isinstance(layers, Mapping) or not layers:
        raise ValueError("Taxonomy failure_layers must be a non-empty object")
    result: dict[str, set[str]] = {}
    for layer, definition in layers.items():
        if not isinstance(layer, str) or not isinstance(definition, Mapping):
            raise ValueError("Taxonomy failure layer is malformed")
        subtypes = definition.get("subtypes")
        if not isinstance(subtypes, list) or not all(
            isinstance(item, str) and item for item in subtypes
        ):
            raise ValueError(f"Taxonomy layer {layer!r} has malformed subtypes")
        result[layer] = set(subtypes)
    return result


def _validate_outcome_axes(
    record: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
    terminal_definition: Mapping[str, Any],
    case_id: str,
) -> None:
    axes = taxonomy.get("outcome_axes")
    if axes is None:
        return
    if not isinstance(axes, Mapping) or not axes:
        raise ValueError("Taxonomy outcome_axes must be a non-empty object")
    for axis, allowed in axes.items():
        if not isinstance(axis, str) or not isinstance(allowed, list) or not all(
            isinstance(item, str) and item for item in allowed
        ):
            raise ValueError("Taxonomy outcome axis is malformed")
        value = _require_string(record, axis)
        if value not in allowed:
            raise ValueError(f"Unknown {axis} {value!r} for {case_id}")

    required = terminal_definition.get("required_axes", {})
    if not isinstance(required, Mapping):
        raise ValueError(f"Terminal axis requirements are malformed for {case_id}")
    for axis, allowed in required.items():
        if axis not in axes or not isinstance(allowed, list):
            raise ValueError(f"Terminal axis requirement is malformed for {case_id}")
        if record.get(axis) not in allowed:
            raise ValueError(
                f"Terminal outcome is inconsistent with {axis} for {case_id}"
            )

    allowed_flags = taxonomy.get("quality_flags", [])
    flags = record.get("quality_flags", [])
    quality_evidence = record.get("quality_evidence", [])
    if not isinstance(allowed_flags, list) or not all(
        isinstance(item, str) and item for item in allowed_flags
    ):
        raise ValueError("Taxonomy quality_flags must be a string list")
    if not isinstance(flags, list) or len(flags) != len(set(flags)):
        raise ValueError(f"Malformed quality flags for {case_id}")
    if any(not isinstance(item, str) or item not in allowed_flags for item in flags):
        raise ValueError(f"Unknown quality flag for {case_id}")
    if not isinstance(quality_evidence, list):
        raise ValueError(f"Malformed quality evidence for {case_id}")
    if flags and not quality_evidence:
        raise ValueError(f"Quality flag lacks evidence for {case_id}")
    for anchor in quality_evidence:
        if not isinstance(anchor, Mapping):
            raise ValueError(f"Malformed quality evidence for {case_id}")
        if not isinstance(anchor.get("artifact_path"), str) or not anchor.get(
            "artifact_path"
        ):
            raise ValueError(f"Quality evidence lacks artifact_path for {case_id}")
        if not isinstance(anchor.get("observation"), str) or not anchor.get(
            "observation"
        ):
            raise ValueError(f"Quality evidence lacks observation for {case_id}")


def validate_classifications(
    records: Sequence[Mapping[str, Any]],
    taxonomy: Mapping[str, Any],
    *,
    expected_case_ids: Iterable[str] | None = None,
) -> None:
    terminal_definitions = taxonomy.get("terminal_outcomes")
    if not isinstance(terminal_definitions, Mapping):
        raise ValueError("Taxonomy terminal_outcomes must be an object")
    layer_subtypes = _failure_subtypes(taxonomy)
    all_subtypes = set().union(*layer_subtypes.values())

    seen: set[str] = set()
    for record in records:
        case_id = _require_string(record, "case_id")
        if case_id in seen:
            raise ValueError(f"Duplicate classification for {case_id}")
        seen.add(case_id)

        if record.get("adjudication_status") != "complete":
            raise ValueError(f"Classification is not complete for {case_id}")
        terminal = _require_string(record, "terminal_outcome")
        terminal_definition = terminal_definitions.get(terminal)
        if not isinstance(terminal_definition, Mapping):
            raise ValueError(f"Unknown terminal outcome {terminal!r} for {case_id}")
        _validate_outcome_axes(record, taxonomy, terminal_definition, case_id)

        bad_case = terminal_definition.get("bad_case") is True
        layer = record.get("primary_failure_layer")
        subtype = record.get("primary_subtype")
        secondary = record.get("secondary_subtypes", [])
        anchors = record.get("evidence_anchors", [])
        if not isinstance(secondary, list) or not all(
            isinstance(item, str) and item for item in secondary
        ):
            raise ValueError(f"Malformed secondary subtypes for {case_id}")
        if len(secondary) > 3 or len(secondary) != len(set(secondary)):
            raise ValueError(
                f"Secondary subtypes violate the frozen policy for {case_id}"
            )
        if any(item not in all_subtypes for item in secondary):
            raise ValueError(f"Unknown secondary subtype for {case_id}")
        if not isinstance(anchors, list):
            raise ValueError(f"Malformed evidence anchors for {case_id}")

        if not bad_case:
            if layer is not None or subtype is not None or secondary or anchors:
                raise ValueError(
                    f"Non-bad terminal outcome cannot carry failure labels for {case_id}"
                )
            continue

        if not isinstance(layer, str) or layer not in layer_subtypes:
            raise ValueError(f"Unknown primary failure layer for {case_id}")
        if not isinstance(subtype, str) or subtype not in layer_subtypes[layer]:
            raise ValueError(f"Primary subtype does not belong to layer for {case_id}")
        if layer != "unresolved" and not anchors:
            raise ValueError(
                f"Non-unresolved classification lacks evidence for {case_id}"
            )
        for anchor in anchors:
            if not isinstance(anchor, Mapping):
                raise ValueError(f"Malformed evidence anchor for {case_id}")
            artifact_path = anchor.get("artifact_path")
            observation = anchor.get("observation")
            if not isinstance(artifact_path, str) or not artifact_path:
                raise ValueError(f"Evidence anchor lacks artifact_path for {case_id}")
            if not isinstance(observation, str) or not observation:
                raise ValueError(f"Evidence anchor lacks observation for {case_id}")

    if expected_case_ids is not None:
        expected = set(expected_case_ids)
        missing = sorted(expected - seen)
        extra = sorted(seen - expected)
        if missing or extra:
            raise ValueError(
                "Classification universe mismatch: "
                f"missing={missing[:5]!r}, extra={extra[:5]!r}"
            )


def select_core_batch(
    records: Sequence[Mapping[str, Any]],
    taxonomy: Mapping[str, Any],
    *,
    expected_case_ids: Iterable[str],
) -> dict[str, Any]:
    validate_classifications(
        records,
        taxonomy,
        expected_case_ids=expected_case_ids,
    )
    policy = taxonomy.get("batch_selection")
    if not isinstance(policy, Mapping):
        raise ValueError("Taxonomy batch_selection must be an object")
    eligible_terminals = policy.get("eligible_terminal_outcomes")
    batch_size = policy.get("batch_size")
    if not isinstance(eligible_terminals, list) or not all(
        isinstance(item, str) for item in eligible_terminals
    ):
        raise ValueError("Malformed eligible terminal outcomes")
    if not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError("Malformed batch size")

    strata: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        if record["terminal_outcome"] not in eligible_terminals:
            continue
        stratum = "|".join(
            (
                str(record["terminal_outcome"]),
                str(record["primary_failure_layer"]),
                str(record["primary_subtype"]),
            )
        )
        strata[stratum].append(record)

    ordered_strata = sorted(strata, key=lambda item: (-len(strata[item]), item))
    ranked: dict[str, list[str]] = {}
    for stratum in ordered_strata:
        ranked[stratum] = sorted(
            (str(record["case_id"]) for record in strata[stratum]),
            key=lambda case_id: (
                hashlib.sha256((CORE_BATCH_SALT + case_id).encode("utf-8")).hexdigest(),
                case_id,
            ),
        )

    selected: list[str] = []
    offsets = {stratum: 0 for stratum in ordered_strata}
    while len(selected) < batch_size:
        added = False
        for stratum in ordered_strata:
            offset = offsets[stratum]
            if offset >= len(ranked[stratum]):
                continue
            selected.append(ranked[stratum][offset])
            offsets[stratum] = offset + 1
            added = True
            if len(selected) == batch_size:
                break
        if not added:
            break

    eligible_case_ids = {
        str(record["case_id"])
        for record in records
        if record["terminal_outcome"] in eligible_terminals
    }
    selected_set = set(selected)
    return {
        "schema_version": "1.0.0",
        "selection_policy": {
            "salt": CORE_BATCH_SALT,
            "batch_size": batch_size,
            "stratum_order": "descending-frequency-then-lexical",
            "within_stratum_order": "ascending-salted-sha256",
            "sampling": "round-robin",
        },
        "eligible_bad_cases": len(eligible_case_ids),
        "strata": [
            {
                "stratum": stratum,
                "count": len(ranked[stratum]),
                "ranked_case_ids": ranked[stratum],
            }
            for stratum in ordered_strata
        ],
        "selected_case_ids": selected,
        "validation_case_ids": sorted(eligible_case_ids - selected_set),
    }
