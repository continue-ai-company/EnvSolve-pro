from __future__ import annotations

from envsolve_harness.certification_repair_analysis import classify_replay_sequence


def _record(status: str, digest: str, *, certified: bool = False) -> dict[str, object]:
    return {
        "replay_id": f"replay-{digest}",
        "status": status,
        "program_sha256": digest,
        "certified": certified,
    }


def test_first_replay_pass_is_not_classified_as_repair() -> None:
    result = classify_replay_sequence(
        [_record("pass", "first", certified=True)],
        official_pass=True,
    )

    assert result["first_replay_pass"] is True
    assert result["repair_opportunity"] is False
    assert result["activated_repair"] is False
    assert result["repair_success"] is False


def test_failure_then_different_pass_activates_successful_repair() -> None:
    result = classify_replay_sequence(
        [
            _record("fail", "first"),
            _record("pass", "second", certified=True),
        ],
        official_pass=True,
    )

    assert result["repair_opportunity"] is True
    assert result["activated_repair"] is True
    assert result["repair_success"] is True


def test_same_program_pass_does_not_count_as_repair() -> None:
    result = classify_replay_sequence(
        [
            _record("unknown", "same"),
            _record("pass", "same", certified=True),
        ],
        official_pass=True,
    )

    assert result["repair_opportunity"] is True
    assert result["activated_repair"] is False


def test_one_shot_limit_record_is_not_an_executed_replay() -> None:
    rejected = {
        **_record("replay_limit", "second"),
        "replay_executed": False,
    }
    result = classify_replay_sequence(
        [_record("fail", "first"), rejected],
        official_pass=False,
    )

    assert result["submission_records"] == 2
    assert result["executed_replays"] == 1
    assert result["replay_limit_rejections"] == 1
    assert result["activated_repair"] is False


def test_censored_network_failure_does_not_activate_repair() -> None:
    result = classify_replay_sequence(
        [
            _record("fail", "dns"),
            _record("pass", "ready", certified=True),
        ],
        official_pass=True,
        infrastructure_censored_replay_ids=frozenset({"replay-dns"}),
    )

    assert result["raw_first_replay_status"] == "fail"
    assert result["infrastructure_censored_replays"] == 1
    assert result["first_replay_status"] == "pass"
    assert result["first_replay_pass"] is True
    assert result["repair_opportunity"] is False
    assert result["activated_repair"] is False


def test_integrity_invalid_pass_does_not_activate_repair() -> None:
    result = classify_replay_sequence(
        [
            _record("fail", "dns"),
            _record("fail", "fake-package"),
            _record("pass", "verifier-wrapper", certified=True),
        ],
        official_pass=True,
        infrastructure_censored_replay_ids=frozenset({"replay-dns"}),
        integrity_invalid_replay_ids=frozenset(
            {"replay-fake-package", "replay-verifier-wrapper"}
        ),
    )

    assert result["executed_replays"] == 3
    assert result["effective_replays"] == 0
    assert result["infrastructure_censored_replays"] == 1
    assert result["integrity_invalid_replays"] == 2
    assert result["first_replay_status"] is None
    assert result["repair_opportunity"] is False
    assert result["activated_repair"] is False
    assert result["repair_success"] is False
