from __future__ import annotations

from copy import deepcopy

from envsolve_harness.audit import _official_primary_advisory_submission_valid


def _metadata() -> dict[str, object]:
    return {
        "runner": "codex-cli-boundary-v5-official-primary-remote-docker",
        "official_primary_submission": {
            "eligible": True,
            "qualification_is_advisory": True,
            "qualification_feedback_returned_to_agent": False,
            "program_sha256": "submitted-script",
        },
        "candidate_validation": {
            "accepted": True,
            "details": {"protected_configuration_history": "no-write-observed"},
        },
        "construction_workspace_integrity": {"valid": True},
        "submission_qualification": {
            "certified": False,
            "status": "fail",
            "feedback_returned_to_agent": False,
        },
        "repository_integrity": {
            "valid": False,
            "violations": [
                {"kind": "submitted_program_qualification_failed"}
            ],
        },
    }


def test_accepts_named_official_primary_advisory_submission() -> None:
    assert _official_primary_advisory_submission_valid(
        _metadata(), {"script": {"sha256": "submitted-script"}}
    )


def test_rejects_advisory_submission_when_safety_or_binding_changes() -> None:
    manifest = {"script": {"sha256": "submitted-script"}}
    mutations = (
        ("runner", "other-runner"),
        ("official_primary_submission.program_sha256", "different-script"),
        ("candidate_validation.accepted", False),
        (
            "candidate_validation.details.protected_configuration_history",
            "write-observed",
        ),
        ("construction_workspace_integrity.valid", False),
        ("submission_qualification.feedback_returned_to_agent", True),
        ("repository_integrity.violations.0.kind", "tracked-source-change"),
    )
    for dotted_path, value in mutations:
        metadata = deepcopy(_metadata())
        target: object = metadata
        parts = dotted_path.split(".")
        for part in parts[:-1]:
            if isinstance(target, list):
                target = target[int(part)]
            else:
                target = target[part]  # type: ignore[index]
        if isinstance(target, list):
            target[int(parts[-1])] = value
        else:
            target[parts[-1]] = value  # type: ignore[index]
        assert not _official_primary_advisory_submission_valid(metadata, manifest)
