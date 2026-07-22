from __future__ import annotations

import hashlib
import json

from envsolve.constraints import (
    ConstraintDomain,
    ConstraintPredicate,
    ConstraintRole,
    NormalizedConstraint,
    build_causal_constraint_frontier,
)
from envsolve.runtime.policy import StructuredModelDeploymentPolicy
from envsolve.runtime.verifier import PythonDeploymentVerifier
from envsolve.solver import CommandResult
from envsolve.state import EnvironmentState


def _module_evidence(
    evidence_id: str,
    *,
    subject: str,
    path: str,
    sequence: int,
) -> dict:
    return {
        "evidence_id": evidence_id,
        "kind": "module-requirement",
        "source": "executable-verifier:synthetic",
        "candidate_id": "candidate-0002",
        "confidence": 1.0,
        "value": {
            "name": subject,
            "present": True,
            "finding_provenance": {
                "path": path,
                "runtime_observation": {
                    "status": "missing",
                    "kind": "missing",
                    "missing_name": "six.moves",
                    "error": "No module named 'six.moves'",
                },
                "evidence": [{"kind": "source-role", "detail": "runtime"}],
            },
        },
        "state_metadata": {"event_sequence": sequence},
    }


def _state_with_amplified_imports() -> EnvironmentState:
    state = EnvironmentState(
        "case",
        case={"case_id": "case", "repository": "owner/repo", "revision": "abc"},
    )
    for index, subject in enumerate(("conans.client", "conans.server"), start=1):
        evidence_id = f"module-evidence-{index}"
        state.evidence[evidence_id] = _module_evidence(
            evidence_id,
            subject=subject,
            path=f"src/{index}.py",
            sequence=index,
        )
        constraint = NormalizedConstraint(
            ConstraintDomain.MODULE,
            subject,
            ConstraintPredicate.PRESENT,
            True,
            ConstraintRole.REQUIREMENT,
            (evidence_id,),
        )
        state.constraints[constraint.constraint_id] = constraint.to_state_fields(
            "violated"
        )
    platform_evidence = "base-platform-machine"
    state.evidence[platform_evidence] = {
        "evidence_id": platform_evidence,
        "kind": "platform-observation",
        "source": "fresh-base-runtime:sha256:image",
        "confidence": 1.0,
        "value": {"name": "machine", "value": "aarch64"},
        "state_metadata": {"event_sequence": 0},
    }
    machine = NormalizedConstraint(
        ConstraintDomain.PLATFORM,
        "machine",
        ConstraintPredicate.EQUALS,
        "aarch64",
        ConstraintRole.FACT,
        (platform_evidence,),
    )
    state.constraints[machine.constraint_id] = machine.to_state_fields("satisfied")
    return state


def test_groups_surface_imports_by_executable_missing_name_without_mutation() -> None:
    state = _state_with_amplified_imports()
    before = state.to_dict()

    frontier = build_causal_constraint_frontier(state)

    assert state.to_dict() == before
    assert frontier["raw_evidence_retained"] is True
    assert frontier["hard_state_mutated"] is False
    assert frontier["latest_module_observation_scope"] == "candidate-0002"
    root = frontier["causal_roots"][0]
    assert root["root_kind"] == "runtime_missing_dependency"
    assert root["subject"] == "six.moves"
    assert root["surface_constraint_count"] == 2
    assert root["surface_subjects"] == ["conans.client", "conans.server"]
    assert root["source_roles"] == {"runtime": 2}
    assert frontier["summary"]["maximum_surface_amplification"] == 2
    assert frontier["observed_environment_facts"][0]["observed"] == "aarch64"
    assert frontier["observed_environment_facts"][0]["trust_levels"] == [
        "fresh_environment"
    ]


def test_newer_resolved_module_observation_retires_older_missing_root() -> None:
    state = _state_with_amplified_imports()
    state.evidence["resolved-newer"] = {
        "evidence_id": "resolved-newer",
        "kind": "module-observation",
        "source": "executable-verifier:synthetic",
        "candidate_id": "candidate-0003",
        "confidence": 1.0,
        "value": {"name": "six.moves", "present": True},
        "state_metadata": {"event_sequence": 10},
    }

    frontier = build_causal_constraint_frontier(state)

    assert frontier["latest_module_observation_scope"] == "candidate-0003"
    assert frontier["causal_roots"] == []
    assert frontier["summary"]["causally_grouped_surface_constraint_count"] == 0


def test_runtime_frontier_persists_until_fresh_verifier_proves_resolution() -> None:
    state = EnvironmentState(
        "case",
        case={"case_id": "case", "repository": "owner/repo", "revision": "abc"},
    )
    state.evidence["pyo3"] = {
        "evidence_id": "pyo3",
        "kind": "action-result",
        "source": "fresh-environment-replay",
        "candidate_id": "candidate-0001",
        "confidence": 1.0,
        "value": {
            "exit_code": 1,
            "stdout": "",
            "stderr": (
                "error: the configured Python interpreter version (3.13) is newer "
                "than PyO3's maximum supported version (3.12)"
            ),
        },
        "state_metadata": {"event_sequence": 10},
    }
    state.evidence["generic"] = {
        "evidence_id": "generic",
        "kind": "action-result",
        "source": "fresh-environment-replay",
        "candidate_id": "candidate-0002",
        "confidence": 1.0,
        "value": {
            "exit_code": 1,
            "stdout": "",
            "stderr": "No matching distribution found for demo",
        },
        "state_metadata": {"event_sequence": 11},
    }
    state.actions["candidate-0002"] = {
        "action_id": "candidate-0002",
        "state_metadata": {"event_sequence": 12},
    }

    roots = build_causal_constraint_frontier(state)["causal_roots"]

    assert len(roots) == 1
    assert roots[0]["root_kind"] == "runtime_compatibility_frontier"
    assert roots[0]["observed_version"] == "3.13"
    assert roots[0]["maximum_supported_version"] == "3.12"
    assert roots[0]["trust_levels"] == ["fresh_execution"]

    state.verifications.append(
        {
            "verification_id": "verification-candidate-0002",
            "details": {
                "candidate_id": "candidate-0002",
                "verifier_details": {
                    "report_details": {
                        "environment_facts": {"python_version": "3.12.13"}
                    }
                },
            },
            "state_metadata": {"event_sequence": 30},
        }
    )

    assert build_causal_constraint_frontier(state)["causal_roots"] == []


def test_runtime_frontier_merges_typed_and_raw_evidence_for_latest_candidate() -> None:
    state = EnvironmentState(
        "case",
        case={"case_id": "case", "repository": "owner/repo", "revision": "abc"},
    )
    message = (
        "the configured Python interpreter version (3.13) is newer than "
        "PyO3's maximum supported version (3.12)"
    )
    state.actions["candidate-0002"] = {
        "action_id": "candidate-0002",
        "state_metadata": {"event_sequence": 20},
    }
    state.evidence["raw"] = {
        "evidence_id": "raw",
        "kind": "action-result",
        "source": "fresh-environment-replay",
        "confidence": 1.0,
        "value": {
            "action_id": "candidate-0002",
            "exit_code": 1,
            "stdout": "",
            "stderr": message,
        },
        "state_metadata": {"event_sequence": 21},
    }
    state.evidence["typed"] = {
        "evidence_id": "typed",
        "kind": "runtime-compatibility-observation",
        "source": "executable-verifier:synthetic",
        "candidate_id": "candidate-0002",
        "confidence": 1.0,
        "value": {
            "provider": "pyo3",
            "runtime": "python",
            "observed_version": "3.13",
            "maximum_supported_version": "3.12",
            "signature": "pyo3-maximum-python",
        },
        "state_metadata": {"event_sequence": 22},
    }

    frontier = build_causal_constraint_frontier(state)

    assert frontier["latest_execution_scope"] == "candidate-0002"
    assert len(frontier["causal_roots"]) == 1
    root = frontier["causal_roots"][0]
    assert root["evidence_ids"] == ["raw", "typed"]
    assert root["evidence_count"] == 2
    assert root["trust_levels"] == ["fresh_execution"]

    state.evidence["typed-later"] = {
        **state.evidence["typed"],
        "evidence_id": "typed-later",
        "candidate_id": "candidate-0003",
        "state_metadata": {"event_sequence": 30},
    }
    later_root = build_causal_constraint_frontier(state)["causal_roots"][0]

    assert later_root["root_id"] == root["root_id"]
    assert later_root["scope_id"] == "candidate-0003"
    assert later_root["observed_scopes"] == ["candidate-0002", "candidate-0003"]


def test_verifier_emits_typed_runtime_compatibility_observation() -> None:
    result = CommandResult(
        1,
        stderr=(
            "error: the configured Python interpreter version (3.13) is newer "
            "than PyO3's maximum supported version (3.12)"
        ),
    )

    observations = PythonDeploymentVerifier._runtime_compatibility_observations(
        result
    )

    assert len(observations) == 1
    assert observations[0].kind == "runtime-compatibility-observation"
    assert observations[0].value["signature"] == "pyo3-maximum-python"
    assert not PythonDeploymentVerifier._runtime_compatibility_observations(
        CommandResult(1, stderr="No matching distribution found for demo")
    )


def test_causal_policy_replaces_flat_surface_list_with_frontier() -> None:
    state = _state_with_amplified_imports()
    common = {
        "model": object(),
        "repository_profile": {"files": [{"path": "pyproject.toml"}]},
        "operation_profile": "free-form",
    }
    policy = StructuredModelDeploymentPolicy(
        common["model"],
        common["repository_profile"],
        operation_profile=common["operation_profile"],
        constraint_profile="causal-frontier",
    )
    flat_policy = StructuredModelDeploymentPolicy(
        object(),
        common["repository_profile"],
        operation_profile="free-form",
    )

    projection = policy._state_projection(state)
    flat_projection = flat_policy._state_projection(state)
    encoded = json.dumps(projection, sort_keys=True)

    assert "active_module_requirements" not in projection
    assert "constraint_frontier" in projection
    assert '"subject": "six.moves"' in encoded
    assert '"surface_constraint_count": 2' in encoded
    assert projection["constraint_conflicts"]["module_surface_conflict_count"] == 0
    shared_keys = set(projection) & set(flat_projection) - {"constraint_conflicts"}
    assert {
        key: projection[key] for key in shared_keys
    } == {
        key: flat_projection[key] for key in shared_keys
    }


class _CandidateModel:
    def invoke(self, messages):
        return type(
            "Response",
            (),
            {
                "content": json.dumps(
                    {
                        "script": "python -m pip install -e .",
                        "rationale": "install the project",
                    }
                )
            },
        )()


def test_causal_candidate_persists_the_exact_frontier_projection() -> None:
    state = _state_with_amplified_imports()
    policy = StructuredModelDeploymentPolicy(
        _CandidateModel(),
        {"files": []},
        operation_profile="free-form",
        constraint_profile="causal-frontier",
    )

    candidate = policy.propose(state)

    snapshot = candidate.metadata["constraint_frontier_snapshot"]
    encoded = json.dumps(
        snapshot,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    assert snapshot["schema_version"] == "1.1.0"
    assert candidate.metadata["constraint_frontier_sha256"] == hashlib.sha256(
        encoded.encode("utf-8")
    ).hexdigest()
