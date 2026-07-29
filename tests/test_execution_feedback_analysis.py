from types import SimpleNamespace

from experiments.analyze_execution_feedback_screen import (
    _apply_interruption_amendments,
    _constraint_progress_metrics,
    _operation_metrics,
    _terminal_class,
)


def test_terminal_class_censors_repository_acquisition_only() -> None:
    terminal_class, censored = _terminal_class(
        generation={
            "generation_completed": False,
            "error": "Unable to acquire the requested repository revision",
        },
        evaluation=None,
    )

    assert terminal_class == (
        "repository-acquisition-infrastructure-censored"
    )
    assert censored is True


def test_terminal_class_keeps_goal_timeout_as_algorithm_failure() -> None:
    terminal_class, censored = _terminal_class(
        generation={
            "generation_completed": False,
            "error": (
                "Executable goal contract exceeded its observation timeout"
            ),
        },
        evaluation=None,
    )

    assert terminal_class == "algorithmic-execution-timeout"
    assert censored is False


def test_terminal_class_censors_measurement_integrity_failure() -> None:
    terminal_class, censored = _terminal_class(
        generation={
            "generation_completed": False,
            "error": (
                "Import alias integrity audit did not produce a valid report"
            ),
        },
        evaluation=None,
    )

    assert terminal_class == "measurement-integrity-censored"
    assert censored is True


def test_operation_metrics_capture_duration_and_editable_extra_breadth() -> None:
    state = SimpleNamespace(
        actions={
            "candidate-0001": {
                "status": "failed",
                "command": (
                    'python -m pip install -e ".[dev,text,vision,audio]"\n'
                ),
                "observation": {"duration_seconds": 12.5},
            },
            "candidate-0002": {
                "status": "running",
                "command": "pip install -e .\n",
            },
        },
        failures={
            "failure-0001": {
                "category": "candidate-validation-reject",
                "message": (
                    "candidate program directly materializes an importable "
                    "artifact"
                ),
            }
        },
    )

    metrics = _operation_metrics(state)

    assert metrics["action_status_counts"] == {
        "failed": 1,
        "running": 1,
    }
    assert metrics["running_action_ids"] == ["candidate-0002"]
    assert metrics["completed_action_duration_seconds"]["maximum"] == 12.5
    assert metrics["maximum_editable_extra_group_count"] == 4
    assert metrics["candidate_validation_reject_count"] == 1


def test_constraint_progress_detects_an_unchanged_nonempty_frontier() -> None:
    state = SimpleNamespace(
        verifications=[
            {
                "details": {
                    "candidate_id": "candidate-0001",
                    "verifier_details": {"finding_ids": ["b", "a"]},
                }
            },
            {
                "details": {
                    "candidate_id": "candidate-0002",
                    "verifier_details": {"finding_ids": ["a", "b"]},
                }
            },
            {
                "details": {
                    "candidate_id": "candidate-0003",
                    "verifier_details": {"finding_ids": ["a"]},
                }
            },
        ]
    )

    metrics = _constraint_progress_metrics(state)

    assert metrics["stagnant_frontier_transition_count"] == 1
    assert metrics["longest_identical_nonempty_finding_set_run"] == 2
    assert metrics["finding_count_sequence"] == [
        {"candidate_id": "candidate-0001", "finding_count": 2},
        {"candidate_id": "candidate-0002", "finding_count": 2},
        {"candidate_id": "candidate-0003", "finding_count": 1},
    ]


def test_interruption_amendment_replaces_only_the_recorded_run_id() -> None:
    preregistration = {
        "study_id": "screen",
        "episodes": [
            {
                "case_id": "case-a",
                "host": "mac",
                "run_id": "original",
            }
        ],
    }
    amendment = {
        "amendment_type": "user-directed-external-interruption",
        "study_id": "screen",
        "source_episode": {
            "case_id": "case-a",
            "primary_metric_eligible": False,
            "run_id": "original",
        },
        "retry": {
            "algorithm_prompt_or_threshold_changed": False,
            "fresh_episode_and_containers": True,
            "inherits_partial_candidate_state": False,
            "run_id": "retry1",
            "same_algorithm_files": True,
            "same_budget_and_timeouts": True,
            "same_case": True,
            "same_host": True,
            "same_model": True,
            "same_seed": True,
        },
    }

    episodes, replacements = _apply_interruption_amendments(
        preregistration,
        [amendment],
    )

    assert preregistration["episodes"][0]["run_id"] == "original"
    assert episodes == [
        {
            "analysis_replacement": (
                "user-directed-external-interruption-retry"
            ),
            "case_id": "case-a",
            "host": "mac",
            "preregistered_run_id": "original",
            "run_id": "retry1",
        }
    ]
    assert replacements == [
        {
            "analyzed_run_id": "retry1",
            "preregistered_run_id": "original",
        }
    ]
