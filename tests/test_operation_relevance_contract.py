from __future__ import annotations

import json

import pytest

from envsolve.runtime.operation_contract import (
    OPERATION_RELEVANCE_CONTRACT_SCHEMA,
    OperationRelevanceContract,
)
from envsolve.runtime.operation_policy import (
    EvidenceDirectedDeploymentPolicy,
)
from envsolve.solver import RecoverablePolicyError
from envsolve.state import EnvironmentState
from envsolve_harness.runners.envsolve_pro import (
    METHOD,
    METHOD_PROFILE,
)
from envsolve_harness.runners.envsolve_p6 import (
    METHOD_CANDIDATE_ANCHOR_PROFILES,
    METHOD_CANDIDATE_INTERFACES,
    METHOD_CONSTRAINT_PROFILES,
    METHOD_ENVIRONMENT_STRATEGIES,
    METHOD_REPOSITORY_EVIDENCE_PROFILES,
)
from envsolve_harness.runners.registry import registered_solver_runners


class _Response:
    def __init__(self, content: str) -> None:
        self.content = content


class _RecordingModel:
    def __init__(self, content: str) -> None:
        self.content = content
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return _Response(self.content)


def _state() -> EnvironmentState:
    return EnvironmentState(
        "case",
        case={
            "case_id": "case",
            "repository": "owner/repository",
            "revision": "abc",
        },
    )


def _finding(finding_id: str, subject: str) -> dict:
    return {
        "finding_id": finding_id,
        "domain": "module",
        "subject": subject,
        "predicate": "present",
        "required": True,
        "observed": False,
        "provenance": {"file": f"src/{subject}.py"},
    }


def _verification(
    candidate_id: str,
    verification_id: str,
    findings: list[dict],
    *,
    complete: bool = True,
) -> dict:
    return {
        "verification_id": verification_id,
        "verifier": "goal",
        "passed": False,
        "details": {
            "candidate_id": candidate_id,
            "reported_passed": False,
            "summary": f"{len(findings)} active findings",
            "verifier_details": {
                "completed": True,
                "goal_passed": False,
                "infrastructure_error": None,
                "report_details": {
                    "goal_report": {
                        "status": "fail",
                        "finding_set_complete": complete,
                        "findings": findings,
                    }
                },
            },
        },
    }


def _contract(
    target_ids: list[str],
    evidence_ids: list[str],
    *,
    tool: str = "python",
    mechanism: str = "install",
    target: str = "project dependencies",
) -> dict:
    return {
        "schema": OPERATION_RELEVANCE_CONTRACT_SCHEMA,
        "target_finding_ids": target_ids,
        "precondition_evidence_ids": evidence_ids,
        "expected_resolved_finding_ids": target_ids,
        "operation_family": {
            "tool": tool,
            "mechanism": mechanism,
            "target": target,
        },
    }


def _policy(model, *, state: EnvironmentState | None = None):
    del state
    return EvidenceDirectedDeploymentPolicy(
        model,
        {"schema": "repository-profile-v1", "files": ["pyproject.toml"]},
        goal_contract={
            "contract_id": "goal",
            "description": "No missing imports",
            "program": "verify",
            "report_schema": "envsolve-goal-report-v1",
            "sha256": "goal-sha",
        },
        operation_profile="evidence-directed",
    )


def _context(policy, state: EnvironmentState) -> dict:
    return policy._state_projection(state)["operation_context"]


def _evidence_id(
    context: dict,
    kind: str,
    *,
    index: int = 0,
    summary_contains: str | None = None,
) -> str:
    matches = [
        item["evidence_id"]
        for item in context["available_precondition_evidence"]
        if item["kind"] == kind
        and (
            summary_contains is None
            or summary_contains in str(item.get("summary"))
        )
    ]
    return matches[index]


def test_contract_rejects_expected_resolution_outside_target() -> None:
    value = _contract(["finding-a"], ["evidence-a"])
    value["expected_resolved_finding_ids"] = ["finding-b"]

    with pytest.raises(ValueError, match="subset"):
        OperationRelevanceContract.from_dict(value)


def test_initial_candidate_uses_goal_target_and_open_program() -> None:
    state = _state()
    probe = _policy(_RecordingModel("{}"))
    context = _context(probe, state)
    target_id = context["active_targets"][0]["finding_id"]
    evidence_id = _evidence_id(context, "repository_profile")
    model = _RecordingModel(
        json.dumps(
            {
                "script": "python -m pip install -e .",
                "rationale": "install the declared project",
                "operation_contract": _contract(
                    [target_id],
                    [evidence_id],
                ),
            }
        )
    )

    candidate = _policy(model).propose(state)

    assert target_id == "goal:goal"
    assert candidate.script == "python -m pip install -e ."
    assert candidate.metadata["operation_profile"] == "evidence-directed"
    assert candidate.metadata["operation_contract"]["target_finding_ids"] == [
        target_id
    ]
    assert "operation_context" in model.messages[1][1]
    assert '"operation_contract"' in model.messages[0][1]
    assert (
        "with string fields \"script\" and\n\"rationale\""
        not in model.messages[0][1]
    )


@pytest.mark.parametrize(
    ("target_id", "evidence_kind", "reason_code"),
    [
        ("finding-that-is-not-active", "execution_feedback", "unknown-target"),
        ("finding-a", "unknown", "unknown-evidence"),
    ],
)
def test_policy_rejects_unknown_contract_references(
    target_id: str,
    evidence_kind: str,
    reason_code: str,
) -> None:
    state = _state()
    state.verifications.append(
        _verification("candidate-0", "verification-0", [_finding("finding-a", "a")])
    )
    probe = _policy(_RecordingModel("{}"))
    context = _context(probe, state)
    evidence_id = (
        "evidence-that-was-not-exposed"
        if evidence_kind == "unknown"
        else _evidence_id(context, evidence_kind)
    )
    model = _RecordingModel(
        json.dumps(
            {
                "script": "python -m pip install dependency",
                "rationale": "repair current finding",
                "operation_contract": _contract([target_id], [evidence_id]),
            }
        )
    )

    with pytest.raises(RecoverablePolicyError) as raised:
        _policy(model).propose(state)

    assert raised.value.category == "candidate-policy-operation-contract"
    assert raised.value.details["reason_code"] == reason_code


def test_policy_rejects_conclusively_failed_exact_script() -> None:
    state = _state()
    state.actions["candidate-1"] = {
        "action_id": "candidate-1",
        "action_type": "deployment-candidate",
        "command": "python -m pip install dependency",
        "metadata": {},
    }
    state.verifications.append(
        _verification("candidate-1", "verification-1", [_finding("finding-a", "a")])
    )
    probe = _policy(_RecordingModel("{}"))
    context = _context(probe, state)
    evidence_id = _evidence_id(context, "execution_feedback")
    model = _RecordingModel(
        json.dumps(
            {
                "script": "python -m pip install dependency",
                "rationale": "retry unchanged",
                "operation_contract": _contract(
                    ["finding-a"],
                    [evidence_id],
                    mechanism="different declared mechanism",
                ),
            }
        )
    )

    with pytest.raises(RecoverablePolicyError) as raised:
        _policy(model).propose(state)

    assert raised.value.details["reason_code"] == "repeated-failed-script"


def _same_family_retry_fixture() -> tuple[
    EnvironmentState,
    EvidenceDirectedDeploymentPolicy,
    dict,
    str,
    str,
]:
    state = _state()
    state.actions["candidate-0"] = {
        "action_id": "candidate-0",
        "action_type": "deployment-candidate",
        "command": "python -m pip install -e .",
        "metadata": {},
    }
    state.verifications.append(
        _verification("candidate-0", "verification-0", [_finding("finding-a", "a")])
    )
    policy = _policy(_RecordingModel("{}"))
    first_context = _context(policy, state)
    prior_evidence_id = _evidence_id(first_context, "execution_feedback")
    prior_contract = _contract(["finding-a"], [prior_evidence_id])
    state.actions["candidate-1"] = {
        "action_id": "candidate-1",
        "action_type": "deployment-candidate",
        "command": "python -m pip install dependency==1",
        "metadata": {"operation_contract": prior_contract},
    }
    state.verifications.append(
        _verification("candidate-1", "verification-1", [_finding("finding-a", "a")])
    )
    current_context = _context(policy, state)
    current_evidence_id = _evidence_id(
        current_context,
        "execution_feedback",
        summary_contains="verification-1:",
    )
    return (
        state,
        policy,
        current_context,
        prior_evidence_id,
        current_evidence_id,
    )


def test_policy_rejects_same_failed_family_without_new_evidence() -> None:
    state, _, _, prior_evidence_id, _ = _same_family_retry_fixture()
    model = _RecordingModel(
        json.dumps(
            {
                "script": "python -m pip install dependency==2",
                "rationale": "same unsupported strategy",
                "operation_contract": _contract(
                    ["finding-a"],
                    [prior_evidence_id],
                ),
            }
        )
    )

    with pytest.raises(RecoverablePolicyError) as raised:
        _policy(model).propose(state)

    assert (
        raised.value.details["reason_code"]
        == "repeated-family-without-new-evidence"
    )


def test_policy_allows_same_family_when_new_execution_evidence_is_cited() -> None:
    state, _, _, prior_evidence_id, current_evidence_id = (
        _same_family_retry_fixture()
    )
    model = _RecordingModel(
        json.dumps(
            {
                "script": "python -m pip install dependency==2",
                "rationale": "revise using the latest execution failure",
                "operation_contract": _contract(
                    ["finding-a"],
                    [prior_evidence_id, current_evidence_id],
                ),
            }
        )
    )

    candidate = _policy(model).propose(state)

    assert candidate.script.endswith("dependency==2")


def test_progress_certificate_uses_only_complete_snapshots_for_resolution() -> None:
    state = _state()
    contract = _contract(
        ["finding-a"],
        ["execution-feedback"],
    )
    state.actions["candidate-1"] = {
        "action_id": "candidate-1",
        "action_type": "deployment-candidate",
        "command": "true",
        "metadata": {
            "operation_contract": contract,
            "operation_active_target_ids_before": [
                "finding-a",
                "finding-b",
            ],
        },
    }
    state.verifications.append(
        _verification(
            "candidate-1",
            "verification-1",
            [_finding("finding-b", "b")],
            complete=True,
        )
    )

    progress = _policy(_RecordingModel("{}"))._operation_progress(state)

    assert progress["conclusive"] is True
    assert progress["status"] == "met"
    assert progress["observed_resolved_finding_ids"] == ["finding-a"]
    assert progress["expected_still_active_finding_ids"] == []

    state.verifications[-1] = _verification(
        "candidate-1",
        "verification-1",
        [_finding("finding-b", "b")],
        complete=False,
    )
    progress = _policy(_RecordingModel("{}"))._operation_progress(state)

    assert progress["conclusive"] is False
    assert progress["status"] == "unknown"
    assert progress["observed_resolved_finding_ids"] == []


def test_operation_context_reserves_space_inside_the_projection_budget() -> None:
    state = _state()
    state.verifications.append(
        _verification(
            "candidate-0",
            "verification-0",
            [
                _finding(f"finding-{index:04d}", f"module_{index}")
                for index in range(200)
            ],
        )
    )
    policy = EvidenceDirectedDeploymentPolicy(
        _RecordingModel("{}"),
        {"files": [{"path": "pyproject.toml", "content": "x" * 20_000}]},
        goal_contract={
            "contract_id": "goal",
            "description": "No missing imports",
            "program": "verify",
            "report_schema": "envsolve-goal-report-v1",
            "sha256": "goal-sha",
        },
        max_feedback_chars=8_192,
    )

    projection = policy._state_projection(state)

    assert len(json.dumps(projection, sort_keys=True)) <= 8_192
    context = projection["operation_context"]
    assert context["active_target_count"] == 200
    assert context["omitted_target_count"] > 0
    assert context["active_targets"]
    assert context["available_precondition_evidence"]


def test_new_method_changes_only_the_operation_profile() -> None:
    assert METHOD == "envsolve-pro-operation-contract"
    assert METHOD_PROFILE == {
        "obligation_profile": "goal-contract",
        "operation_profile": "evidence-directed",
        "constraint_profile": "flat",
        "repository_evidence_profile": "constraint-routed",
        "candidate_anchor_profile": "retained-admissible",
        "candidate_interface": "open-program",
        "candidate_retention": "best-admissible",
        "environment_strategy": "fresh-candidate",
    }
    control = "envsolve-pro-goal-contract-evidence-anchor"
    assert METHOD_PROFILE["constraint_profile"] == (
        METHOD_CONSTRAINT_PROFILES[control]
    )
    assert METHOD_PROFILE["repository_evidence_profile"] == (
        METHOD_REPOSITORY_EVIDENCE_PROFILES[control]
    )
    assert METHOD_PROFILE["candidate_anchor_profile"] == (
        METHOD_CANDIDATE_ANCHOR_PROFILES[control]
    )
    assert METHOD_PROFILE["candidate_interface"] == (
        METHOD_CANDIDATE_INTERFACES[control]
    )
    assert METHOD_PROFILE["environment_strategy"] == (
        METHOD_ENVIRONMENT_STRATEGIES[control]
    )
    assert "envsolve-pro" in registered_solver_runners()
