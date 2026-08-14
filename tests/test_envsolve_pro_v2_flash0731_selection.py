from __future__ import annotations

from experiments.tools.select_envsolve_pro_v2_flash0731_dev16 import (
    MODEL,
    TAKE,
    arm_order,
    build_episodes,
    select_case_ids,
)


def test_selection_is_deterministic_and_identity_only() -> None:
    case_ids = [f"case-{index:02d}" for index in range(44)]

    selected, remaining = select_case_ids(case_ids)
    selected_again, remaining_again = select_case_ids(list(reversed(case_ids)))

    assert len(selected) == TAKE
    assert len(remaining) == 44 - TAKE
    assert selected == selected_again
    assert remaining == remaining_again
    assert set(selected).isdisjoint(remaining)


def test_schedule_is_paired_and_pins_flash_snapshot() -> None:
    selected = [f"case-{index:02d}" for index in range(TAKE)]

    episodes = build_episodes(selected)

    assert len(episodes) == 2 * TAKE
    assert [episode["position"] for episode in episodes] == list(range(1, 33))
    for case_id in selected:
        pair = [episode for episode in episodes if episode["case_id"] == case_id]
        assert len(pair) == 2
        assert {episode["arm"] for episode in pair} == {"A-F", "B-FSR"}
        assert {episode["model"] for episode in pair} == {MODEL}
        assert [episode["arm"] for episode in pair] == [
            arm["arm"] for arm in arm_order(case_id)
        ]


def test_moving_flash_alias_is_not_selected() -> None:
    assert MODEL == "deepseek/deepseek-v4-flash-0731"
    assert "latest" not in MODEL
