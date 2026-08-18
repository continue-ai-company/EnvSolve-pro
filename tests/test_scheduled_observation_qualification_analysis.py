from __future__ import annotations

from copy import deepcopy

from experiments.analyze_scheduled_observation_qualification import (
    CONTROL_ARM,
    TREATMENT_ARM,
    _adjudicate,
    _pairs,
    _scheduled_mechanism,
)


def _observation(
    number: int,
    trigger: str,
    shell_count: int,
    parent: str | None = None,
) -> dict[str, object]:
    event: dict[str, object] = {
        "event": "compatibility_observation",
        "request_index": 0 if trigger == "initial" else number,
        "observation_number": number,
        "trigger": trigger,
        "shell_operations_completed": shell_count,
        "feedback_delivery": "same-active-model-session",
        "result": {
            "ok": True,
            "finding_set_complete": True,
            "operation_constraints_added": False,
        },
    }
    if parent is not None:
        event["parent_tool_call_id"] = parent
    return event


def _tool_result(
    call_id: str,
    name: str,
    observation: dict[str, object] | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {"ok": True}
    if observation is not None:
        result["scheduled_compatibility_observation"] = {
            "observation_number": observation["observation_number"]
        }
    return {
        "event": "tool_result",
        "tool_call_id": call_id,
        "tool_name": name,
        "result": result,
    }


def _valid_events() -> list[dict[str, object]]:
    initial = _observation(1, "initial", 0)
    periodic = _observation(2, "periodic", 16, "s16")
    pre_replay = _observation(3, "pre-replay-dirty", 17, "r1")
    events: list[dict[str, object]] = [
        initial,
        {"event": "provider_response", "request_index": 1},
    ]
    events.extend(
        _tool_result(f"s{index}", "envbench_shell") for index in range(1, 16)
    )
    events.extend(
        [
            periodic,
            _tool_result("s16", "envbench_shell", periodic),
            _tool_result("s17", "envbench_shell"),
            pre_replay,
            _tool_result("r1", "submit_and_replay", pre_replay),
        ]
    )
    return events


def _valid_metadata() -> dict[str, object]:
    return {
        "scheduled_observation": {
            "schedule_compliant": True,
            "cadence_shell_operations": 16,
            "observation_count": 3,
            "operation_constraints_added": False,
            "stores_container_checkpoint": False,
        }
    }


def test_mechanism_recomputes_all_three_scheduled_triggers_from_events() -> None:
    result = _scheduled_mechanism(_valid_events(), _valid_metadata())

    assert result["schedule_compliant"] is True
    assert result["schedule_errors"] == []
    assert result["trigger_counts"] == {
        "initial": 1,
        "periodic": 1,
        "pre-replay-dirty": 1,
    }
    assert result["complete_observation_rate"] == 1.0
    assert result["optional_tool_call_count"] == 0


def test_mechanism_rejects_missing_periodic_event_even_if_metadata_claims_success() -> None:
    events = [
        event
        for event in _valid_events()
        if not (
            event.get("event") == "compatibility_observation"
            and event.get("trigger") == "periodic"
        )
    ]
    result = _scheduled_mechanism(events, _valid_metadata())

    assert result["schedule_compliant"] is False
    assert "periodic-observation-schedule-mismatch" in result["schedule_errors"]
    assert "metadata-observation-count-mismatch" in result["schedule_errors"]


def _record(pair: int, arm: str, official: bool) -> dict[str, object]:
    mechanism = {
        "event_observation_count": 3 if arm == TREATMENT_ARM else 0,
        "complete_observation_count": 3 if arm == TREATMENT_ARM else 0,
        "schedule_compliant": True,
        "optional_tool_call_count": 0,
        "operation_constraint_violations": 0,
        "stores_container_checkpoint": False,
    }
    return {
        "pair_id": f"pair-{pair}",
        "arm": arm,
        "censored": False,
        "candidate_formed": True,
        "official_pass": official,
        "pre_candidate": {
            "model_requests": 10,
            "interactive_tool_steps": 10,
            "total_tokens": 100,
            "seconds_to_certificate": 100,
        },
        "mechanism": mechanism,
    }


def test_adjudication_promotes_only_after_mechanism_and_directional_signal() -> None:
    records: list[dict[str, object]] = []
    for pair in range(8):
        records.append(_record(pair, CONTROL_ARM, official=pair != 0))
        records.append(_record(pair, TREATMENT_ARM, official=True))
    pairs = _pairs(records)  # type: ignore[arg-type]

    positive = _adjudicate(records, pairs)  # type: ignore[arg-type]
    broken = deepcopy(records)
    broken[1]["mechanism"]["schedule_compliant"] = False  # type: ignore[index]
    negative = _adjudicate(broken, _pairs(broken))  # type: ignore[arg-type]

    assert (
        positive["decision"]
        == "positive-directional-promote-to-frozen-dev-evaluation"
    )
    assert positive["mechanism_acceptance"]["passed"] is True
    assert negative["decision"] == "negative-mechanism-not-qualified"
