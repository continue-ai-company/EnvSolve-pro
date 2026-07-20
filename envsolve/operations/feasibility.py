from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def verified_failed_operation_prefix(
    verifications: Sequence[Mapping[str, Any]],
    candidate_id: str,
    command: str,
) -> tuple[str, ...] | None:
    """Return the verifier-grounded prefix ending at an exact failed command."""
    for verification in reversed(verifications):
        if verification.get("passed") is not False:
            continue
        details = verification.get("details")
        if (
            not isinstance(details, Mapping)
            or details.get("candidate_id") != candidate_id
        ):
            continue
        verifier_details = details.get("verifier_details")
        failed_action = (
            verifier_details.get("failed_candidate_action")
            if isinstance(verifier_details, Mapping)
            else None
        )
        if not isinstance(failed_action, Mapping):
            continue
        action_index = failed_action.get("action_index")
        prefix = failed_action.get("prefix_commands")
        if (
            isinstance(action_index, bool)
            or not isinstance(action_index, int)
            or not isinstance(prefix, list)
            or not prefix
            or not all(isinstance(item, str) for item in prefix)
            or action_index != len(prefix) - 1
            or prefix[action_index] != command
            or failed_action.get("command") != command
        ):
            continue
        return tuple(prefix)
    return None
