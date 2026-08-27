from __future__ import annotations

from unittest import mock

from envsolve.runtime import ExecutableGoalContract
from envsolve_harness.current_goal import CurrentGoalService


def test_current_goal_projects_only_current_constraints_without_cross_call_state() -> None:
    raw_results = iter(
        [
            {
                "ok": True,
                "goal_status": "fail",
                "finding_set_complete": True,
                "candidate_ready": False,
                "current": {
                    "obligation_count": 1,
                    "obligation_set_sha256": "not-model-visible",
                    "obligations": [
                        {
                            "domain": "module",
                            "subject": "missing_package",
                            "predicate": "present",
                            "required": True,
                        }
                    ],
                },
                "delta_from_previous": {"classification": "initial"},
                "frontier": {"size": 1},
                "goal_output": {
                    "stdout": {
                        "byte_count": 3,
                        "sha256": "not-model-visible",
                        "tail": "bad",
                        "truncated": False,
                    },
                    "stderr": {"byte_count": 0, "tail": "", "truncated": False},
                },
            },
            {
                "ok": True,
                "goal_status": "pass",
                "finding_set_complete": True,
                "candidate_ready": True,
                "current": {
                    "obligation_count": 0,
                    "obligations": [],
                },
            },
        ]
    )
    transports: list[object] = []

    class Transport:
        def __init__(self, *args: object) -> None:
            transports.append(self)

        def check(self, call_id: str) -> dict[str, object]:
            return next(raw_results)

    contract = ExecutableGoalContract("goal", "test goal", "true")
    with mock.patch(
        "envsolve_harness.current_goal.CompatibilityLedgerService",
        Transport,
    ):
        service = CurrentGoalService(contract, object())  # type: ignore[arg-type]
        failed = service.check("check-1")
        passed = service.check("check-2")

    assert len(transports) == 2
    assert failed["active_constraint_count"] == 1
    assert failed["active_constraints"][0]["subject"] == "missing_package"
    assert passed["candidate_ready"] is True
    assert passed["active_constraints"] == []
    for result in (failed, passed):
        assert result["history_used"] is False
        assert result["stores_container_checkpoint"] is False
        assert "delta_from_previous" not in result
        assert "frontier" not in result
        assert "obligation_set_sha256" not in result
        assert "environment" not in result
        assert "sha256" not in repr(result)
    assert failed["goal_output"]["stdout"] == {
        "byte_count": 3,
        "tail": "bad",
        "truncated": False,
    }
    assert service.metadata() == {
        "schema": "envsolve-current-goal-observation-v1",
        "check_count": 2,
        "complete_check_count": 2,
        "pass_check_count": 1,
        "agent_invoked_only": True,
        "automatic_check_count": 0,
        "history_used": False,
        "cross_call_state_retained": False,
        "stores_container_checkpoint": False,
        "operation_constraints_added": False,
    }


def test_current_goal_preserves_executable_unknown_evidence() -> None:
    class Transport:
        def __init__(self, *args: object) -> None:
            pass

        def check(self, call_id: str) -> dict[str, object]:
            return {
                "ok": False,
                "goal_status": "unknown",
                "finding_set_complete": False,
                "candidate_ready": False,
                "reason": "compatibility probe timed out",
                "execution": {"timed_out": True},
            }

    with mock.patch(
        "envsolve_harness.current_goal.CompatibilityLedgerService",
        Transport,
    ):
        service = CurrentGoalService(
            ExecutableGoalContract("goal", "test goal", "true"),
            object(),  # type: ignore[arg-type]
        )
        result = service.check("check")

    assert result["ok"] is False
    assert result["reason"] == "compatibility probe timed out"
    assert result["execution"] == {"timed_out": True}
    assert result["active_constraints"] == []
