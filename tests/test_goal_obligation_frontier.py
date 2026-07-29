from __future__ import annotations

import json

from envsolve.constraints.goal_frontier import (
    build_goal_obligation_frontier,
    build_model_goal_obligation_frontier,
    ordered_active_goal_findings,
    source_role,
)
from envsolve.runtime.goal_frontier_policy import (
    GOAL_FRONTIER_PROFILE,
    GoalFrontierDeploymentPolicy,
)
from envsolve.state import EnvironmentState


def _finding(
    finding_id: str,
    subject: str,
    path: str,
    *,
    observed: bool | None = False,
) -> dict:
    return {
        "finding_id": finding_id,
        "domain": "module",
        "subject": subject,
        "predicate": "present",
        "required": True,
        "observed": observed,
        "provenance": {
            "file": f"/data/project/owner__repo@abc/{path}",
            "rule": "reportMissingImports",
        },
    }


def _state() -> EnvironmentState:
    state = EnvironmentState(
        "case",
        case={
            "case_id": "case",
            "repository": "owner/repo",
            "revision": "abc",
        },
    )
    findings = [
        _finding("request-runtime", "requests", "src/client.py"),
        _finding(
            "request-runtime-submodule",
            "requests.sessions",
            "src/client.py",
        ),
        _finding(
            "request-build",
            "requests",
            "build/lib/src/client.py",
        ),
        _finding(
            "request-build-submodule",
            "requests.sessions",
            "build/lib/src/client.py",
        ),
        _finding("pytest-test", "pytest", "tests/test_client.py"),
        _finding("sphinx-doc", "sphinx", "docs/conf.py"),
        _finding("resolved", "click", "src/cli.py", observed=True),
        _finding("unknown", "mystery", "examples/demo.py", observed=None),
    ]
    state.verifications.append(
        {
            "verification_id": "verification-candidate-0001",
            "passed": False,
            "details": {
                "candidate_id": "candidate-0001",
                "reported_passed": False,
                "verifier_details": {
                    "report_details": {
                        "goal_report": {
                            "status": "fail",
                            "finding_set_complete": True,
                            "findings": findings,
                        }
                    }
                },
            },
        }
    )
    return state


def test_source_role_preserves_generated_and_optional_surfaces() -> None:
    assert source_role("/repo/build/lib/package.py") == "generated"
    assert source_role("/repo/tests/test_package.py") == "test"
    assert source_role("/repo/docs/conf.py") == "docs"
    assert source_role("/repo/examples/demo.py") == "example"
    assert source_role("/repo/src/package.py") == "runtime"
    assert source_role(None) == "unknown"


def test_frontier_compresses_surface_findings_without_waiving_them() -> None:
    state = _state()
    before = state.to_dict()

    frontier = build_goal_obligation_frontier(state)

    assert state.to_dict() == before
    assert frontier["finding_set_complete"] is True
    assert frontier["raw_findings_retained"] is True
    assert frontier["hard_state_mutated"] is False
    assert frontier["summary"] == {
        "active_finding_count": 6,
        "unknown_finding_count": 1,
        "obligation_group_count": 3,
        "compression_ratio": 2.0,
    }
    requests = frontier["obligation_groups"][0]
    assert requests["subject"] == "requests"
    assert requests["goal_obligation"] is True
    assert requests["action_mapping_grounded"] is False
    assert requests["surface_finding_count"] == 4
    assert requests["distinct_surface_subject_count"] == 2
    assert requests["source_roles"] == {"generated": 2, "runtime": 2}
    assert requests["canonical_source_occurrence_count"] == 2
    assert requests["duplicate_surface_occurrence_count"] == 2
    assert requests["surface_subjects"] == ["requests", "requests.sessions"]
    assert [item["subject"] for item in frontier["obligation_groups"]] == [
        "requests",
        "pytest",
        "sphinx",
    ]


def test_repository_routing_uses_one_runtime_first_representative_per_root() -> None:
    findings = ordered_active_goal_findings(_state())

    assert [item["subject"] for item in findings] == [
        "requests",
        "pytest",
        "sphinx",
    ]
    assert findings[0]["finding_id"] == "request-runtime"


def test_model_frontier_stays_structured_under_a_tight_budget() -> None:
    projection = build_model_goal_obligation_frontier(
        _state(),
        max_chars=1_650,
    )
    encoded = json.dumps(projection, ensure_ascii=True, sort_keys=True)

    assert len(encoded) <= 1_650
    assert projection["summary"]["active_finding_count"] == 6
    assert projection["summary"]["obligation_group_count"] == 3
    assert projection["summary"]["obligation_groups_included"] > 0
    assert projection["summary"]["obligation_groups_omitted"] > 0
    assert projection["summary"]["projection_complete"] is False


class _CaptureModel:
    def __init__(self) -> None:
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return type(
            "Response",
            (),
            {
                "content": json.dumps(
                    {
                        "script": "python -m pip install -e .",
                        "rationale": "install declared project dependencies",
                    }
                )
            },
        )()


def test_goal_frontier_policy_keeps_open_program_interface() -> None:
    model = _CaptureModel()
    policy = GoalFrontierDeploymentPolicy(
        model,
        {"files": []},
        goal_contract={"contract_id": "goal"},
        operation_profile="free-form",
        constraint_profile="flat",
        max_feedback_chars=24_000,
    )

    candidate = policy.propose(_state())

    projection = candidate.metadata["model_input_projection"]
    assert "active_module_requirements" not in projection
    assert "goal_obligation_frontier" in projection
    assert projection["constraint_conflicts"][
        "module_surface_conflict_count"
    ] == 0
    diagnostic = projection["verification_feedback"][0]["diagnostic"]
    findings = diagnostic["report_details"]["goal_report"]["findings"]
    assert findings["omitted_from_raw_feedback"] is True
    assert findings["count"] == 8
    assert candidate.metadata["constraint_profile"] == GOAL_FRONTIER_PROFILE
    assert (
        candidate.metadata["generator"]
        == "goal-frontier-model-policy-v1"
    )
    assert "operation_contract" not in candidate.metadata
    assert "Return exactly one JSON object" in model.messages[0][1]
    assert '"script" and' in model.messages[0][1]
    assert '"rationale"' in model.messages[0][1]
    assert "namespace is not necessarily an installable distribution" in (
        model.messages[0][1]
    )
