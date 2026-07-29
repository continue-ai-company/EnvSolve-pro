from __future__ import annotations

import json

from envsolve.analysis.bootstrap_failures import (
    bootstrap_strategy,
    classify_bootstrap_failure,
    runtime_branches,
)
from envsolve.constraints.bootstrap_frontier import (
    build_bootstrap_contradiction_frontier,
    build_model_bootstrap_contradiction_frontier,
)
from envsolve.runtime.bootstrap_frontier_policy import (
    BOOTSTRAP_FRONTIER_PROFILE,
    BootstrapFrontierDeploymentPolicy,
)
from envsolve.state import EnvironmentState


def _state() -> EnvironmentState:
    state = EnvironmentState(
        "case",
        case={
            "case_id": "case",
            "repository": "owner/repo",
            "revision": "abc",
        },
    )
    scripts = (
        "python3 -m venv .venv\npip install -e .",
        "python3 -m venv .venv\npip install --no-build-isolation -e .",
        (
            "python3 -m venv .venv\n"
            "pip install pybind11\n"
            "pip install --no-build-isolation -e ."
        ),
    )
    errors = (
        (
            'AttributeError: module "pkgutil" has no attribute '
            "'ImpImporter'\n/usr/local/lib/python3.13/site-packages/x.py"
        ),
        (
            "ModuleNotFoundError: No module named 'pybind11'\n"
            "/usr/local/lib/python3.13/site-packages/x.py"
        ),
        (
            'AttributeError: module "pkgutil" has no attribute '
            "'ImpImporter'\n/usr/local/lib/python3.13/site-packages/y.py"
        ),
    )
    for index, (script, stderr) in enumerate(zip(scripts, errors), start=1):
        candidate_id = f"candidate-{index:04d}"
        state.actions[candidate_id] = {
            "action_id": candidate_id,
            "command": script,
            "status": "failed",
            "exit_code": 1,
            "observation": {
                "stdout": "",
                "stderr": stderr,
                "duration_seconds": index * 10.0,
            },
            "state_metadata": {"event_sequence": index},
        }
        state.verifications.append(
            {
                "verification_id": f"verification-{candidate_id}",
                "passed": False,
                "details": {
                    "candidate_id": candidate_id,
                    "bootstrap_exit_code": 1,
                    "summary": (
                        "Candidate did not return control to the executable goal"
                    ),
                },
            }
        )
    return state


def test_failure_observation_is_conservative_and_runtime_aware() -> None:
    failure = classify_bootstrap_failure(
        "",
        (
            "AttributeError: module 'pkgutil' has no attribute "
            "'ImpImporter'\n/usr/local/lib/python3.13/site-packages/x.py"
        ),
    )

    assert failure.failure_class == "removed-runtime-api"
    assert failure.subject == "pkgutil.ImpImporter"
    assert runtime_branches(
        "python3 -m venv .venv",
        "",
        "/usr/local/lib/python3.13/site-packages/x.py",
    ) == ("3.13",)
    assert runtime_branches(
        "python3.11 -m venv .venv",
        "",
        "/usr/local/lib/python3.13/site-packages/x.py",
    ) == ("3.11",)


def test_strategy_exposes_decisions_without_prescribing_operations() -> None:
    assert bootstrap_strategy(
        "python3 -m venv .venv\npip install --no-build-isolation -e ."
    ) == {
        "artifact_policy": "provider-default",
        "build_isolation": "disabled",
        "dependency_mode": "declared-project-dependencies",
        "environment_provider": "venv",
    }
    assert bootstrap_strategy(
        "python3.11 -m venv .venv\npip install --only-binary=:all: --no-deps -e ."
    ) == {
        "artifact_policy": "binary-required",
        "build_isolation": "default",
        "dependency_mode": "project-without-dependencies",
        "environment_provider": "venv",
    }


def test_frontier_marks_search_dominance_without_hard_infeasibility() -> None:
    state = _state()
    before = state.to_dict()

    frontier = build_bootstrap_contradiction_frontier(state)

    assert state.to_dict() == before
    assert frontier["raw_execution_feedback_retained"] is True
    assert frontier["hard_state_mutated"] is False
    assert frontier["inference_semantics"]["operation_space_closed"] is False
    assert frontier["summary"] == {
        "observed_attempt_count": 3,
        "failed_bootstrap_count": 3,
        "successful_bootstrap_count": 0,
        "infrastructure_censored_count": 0,
        "runtime_branch_count": 1,
        "search_dominated_branch_count": 1,
        "repeated_failure_signature_count": 1,
    }
    branch = frontier["runtime_branches"][0]
    assert branch["runtime_branch"] == "3.13"
    assert branch["search_status"] == "search-dominated-by-observed-failures"
    assert branch["distinct_failed_strategy_count"] == 2
    assert branch["repeated_failure_signature_count"] == 1
    assert frontier["repeated_failures"][0]["occurrence_count"] == 2


def test_successful_bootstrap_overrides_failure_only_search_pressure() -> None:
    state = _state()
    candidate_id = "candidate-0004"
    state.actions[candidate_id] = {
        "action_id": candidate_id,
        "command": (
            "python3 -m venv .venv\n"
            "pip install latest-dependencies\n"
            "pip install --no-deps -e ."
        ),
        "status": "succeeded",
        "exit_code": 0,
        "observation": {
            "stdout": "/usr/local/lib/python3.13/site-packages",
            "stderr": "",
            "duration_seconds": 40.0,
        },
        "state_metadata": {"event_sequence": 4},
    }
    state.verifications.append(
        {
            "verification_id": f"verification-{candidate_id}",
            "passed": False,
            "details": {
                "candidate_id": candidate_id,
                "bootstrap_exit_code": 0,
                "summary": "Executable goal reported unresolved findings",
            },
        }
    )

    branch = build_bootstrap_contradiction_frontier(state)[
        "runtime_branches"
    ][0]

    assert branch["search_status"] == "bootstrap-observed-feasible"
    assert branch["successful_bootstrap_count"] == 1


def test_network_failure_is_censored_and_cannot_dominate_a_branch() -> None:
    state = _state()
    for index in range(4, 7):
        candidate_id = f"candidate-{index:04d}"
        state.actions[candidate_id] = {
            "action_id": candidate_id,
            "command": (
                "python3.11 -m venv .venv\n"
                "apt-get install build-essential"
            ),
            "status": "failed",
            "exit_code": 1,
            "observation": {
                "stdout": "",
                "stderr": "E: Failed to fetch package 502 Bad Gateway",
                "duration_seconds": 10.0,
            },
            "state_metadata": {"event_sequence": index},
        }
        state.verifications.append(
            {
                "verification_id": f"verification-{candidate_id}",
                "passed": False,
                "details": {
                    "candidate_id": candidate_id,
                    "bootstrap_exit_code": 1,
                    "summary": (
                        "Candidate did not return control to the executable goal"
                    ),
                },
            }
        )

    frontier = build_bootstrap_contradiction_frontier(state)
    branch = next(
        item
        for item in frontier["runtime_branches"]
        if item["runtime_branch"] == "3.11"
    )

    assert frontier["summary"]["infrastructure_censored_count"] == 3
    assert branch["infrastructure_censored_count"] == 3
    assert branch["failed_attempt_count"] == 0
    assert branch["search_status"] == "unobserved"


def test_model_frontier_remains_structured_under_budget() -> None:
    projection = build_model_bootstrap_contradiction_frontier(
        _state(),
        max_chars=2_600,
    )

    assert len(json.dumps(projection, sort_keys=True)) <= 2_600
    assert projection["summary"]["observed_attempt_count"] == 3
    assert projection["runtime_branches"][0]["runtime_branch"] == "3.13"


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
                        "script": "python3.11 -m venv .venv",
                        "rationale": "change the runtime branch",
                    }
                )
            },
        )()


def test_policy_adds_soft_frontier_and_keeps_open_program_interface() -> None:
    model = _CaptureModel()
    policy = BootstrapFrontierDeploymentPolicy(
        model,
        {"files": []},
        goal_contract={"contract_id": "goal"},
        operation_profile="free-form",
        constraint_profile="flat",
        max_feedback_chars=32_000,
    )

    candidate = policy.propose(_state())

    projection = candidate.metadata["model_input_projection"]
    frontier = projection["bootstrap_contradiction_frontier"]
    assert frontier["summary"]["search_dominated_branch_count"] == 1
    assert candidate.metadata["constraint_profile"] == BOOTSTRAP_FRONTIER_PROFILE
    assert candidate.metadata["generator"] == "bootstrap-frontier-model-policy-v2"
    assert "operation_contract" not in candidate.metadata
    assert "not logically impossible" in model.messages[0][1]
    assert "one open, complete cumulative Bash program" in model.messages[0][1]
