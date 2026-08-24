from __future__ import annotations

from envsolve.solver import (
    CommandResult,
    CounterexampleEvidence,
    ExecutableVerification,
    FeedbackChannel,
)
from envsolve_harness.replay_obligation_ledger import (
    REPLAY_OBLIGATION_SNAPSHOT_SCHEMA,
    ObligationSnapshotCleanReplayService,
    ReplayObligationLedger,
    verification_obligation_snapshot,
)


def _verification(
    *,
    passed: bool | None,
    exit_code: int = 0,
    complete: bool = False,
    counterexamples: tuple[CounterexampleEvidence, ...] = (),
) -> ExecutableVerification:
    return ExecutableVerification(
        verifier="test-verifier",
        check_profile="test-v1",
        channel=FeedbackChannel.INTERNAL_EXECUTION,
        passed=passed,
        bootstrap=CommandResult(exit_code, "", "failure", 1.0),
        summary="test result",
        counterexamples=counterexamples,
        details={"finding_set_complete": complete},
    )


def _replay(outcome: ExecutableVerification) -> dict[str, object]:
    return {
        "status": "pass" if outcome.passed else "fail",
        "phase": "clean-replay",
        "verification": {
            "obligation_snapshot": verification_obligation_snapshot(outcome)
        },
    }


def test_clean_replay_serialization_attaches_obligation_snapshot() -> None:
    service = object.__new__(ObligationSnapshotCleanReplayService)
    service.max_output_chars = 16_000
    outcome = _verification(
        passed=False,
        complete=True,
        counterexamples=(
            CounterexampleEvidence(
                "module-requirement",
                {"name": "demo", "present": True, "finding_id": "demo"},
            ),
            CounterexampleEvidence(
                "module-observation",
                {"name": "demo", "present": False, "finding_id": "demo"},
            ),
        ),
    )

    serialized = service._verification(outcome)

    assert serialized["obligation_snapshot"]["coverage"] == (
        "complete-goal-failure"
    )
    assert serialized["obligation_snapshot"]["obligations"][0]["subject"] == (
        "demo"
    )
    assert serialized["counterexamples"]["truncated"] is False


def test_extracts_all_structured_goal_obligations() -> None:
    outcome = _verification(
        passed=False,
        complete=True,
        counterexamples=(
            CounterexampleEvidence(
                "module-requirement",
                {"name": "demo.api", "present": True, "finding_id": "f1"},
            ),
            CounterexampleEvidence(
                "module-observation",
                {"name": "demo.api", "present": False, "finding_id": "f1"},
            ),
            CounterexampleEvidence(
                "module-requirement",
                {"name": "other", "present": True, "finding_id": "f2"},
            ),
            CounterexampleEvidence(
                "module-observation",
                {"name": "other", "present": False, "finding_id": "f2"},
            ),
        ),
    )

    snapshot = verification_obligation_snapshot(outcome)

    assert snapshot["coverage"] == "complete-goal-failure"
    assert [item["subject"] for item in snapshot["obligations"]] == [
        "demo.api",
        "other",
    ]
    assert all(item["required"] is True for item in snapshot["obligations"])
    assert all(item["observed"] is False for item in snapshot["obligations"])


def test_extracts_provider_and_bootstrap_obligations() -> None:
    provider = _verification(
        passed=False,
        counterexamples=(
            CounterexampleEvidence(
                "import-provider-provenance",
                {"violations": [{"module": "gfosd", "artifact_path": "/tmp/x"}]},
            ),
        ),
    )
    bootstrap = _verification(passed=False, exit_code=1)

    provider_snapshot = verification_obligation_snapshot(provider)
    bootstrap_snapshot = verification_obligation_snapshot(bootstrap)

    assert provider_snapshot["obligations"][0]["subject"] == "gfosd"
    assert provider_snapshot["obligations"][0]["predicate"] == (
        "installed_distribution_owned"
    )
    assert bootstrap_snapshot["obligations"][0]["subject"] == (
        "complete-bootstrap-program"
    )
    assert bootstrap_snapshot["obligations"][0]["observed"] == 1


def test_partial_evidence_preserves_and_complete_evidence_retires_obligations() -> None:
    ledger = ReplayObligationLedger()
    missing_a = _verification(
        passed=False,
        complete=True,
        counterexamples=(
            CounterexampleEvidence(
                "module-requirement",
                {"name": "a", "present": True, "finding_id": "a"},
            ),
            CounterexampleEvidence(
                "module-observation",
                {"name": "a", "present": False, "finding_id": "a"},
            ),
        ),
    )
    bootstrap_failure = _verification(passed=False, exit_code=1)
    missing_b = _verification(
        passed=False,
        complete=True,
        counterexamples=(
            CounterexampleEvidence(
                "module-requirement",
                {"name": "b", "present": True, "finding_id": "b"},
            ),
            CounterexampleEvidence(
                "module-observation",
                {"name": "b", "present": False, "finding_id": "b"},
            ),
        ),
    )

    first = ledger.update(_replay(missing_a))
    partial = ledger.update(_replay(bootstrap_failure))
    complete = ledger.update(_replay(missing_b))
    passed = ledger.update(_replay(_verification(passed=True, complete=True)))

    assert first["active_obligation_count"] == 1
    assert partial["active_obligation_count"] == 2
    assert partial["delta"]["preserved_unobserved"]["count"] == 1
    assert complete["active_obligation_count"] == 1
    assert complete["active_obligations"][0]["obligation"]["subject"] == "b"
    assert complete["delta"]["resolved"]["count"] == 2
    assert {
        item["obligation"]["subject"]
        for item in complete["delta"]["resolved"]["items"]
    } == {"a", "complete-bootstrap-program"}
    assert passed["active_obligation_count"] == 0
    assert ledger.metadata()["resolved_count"] == 3


def test_unknown_and_candidate_validation_preserve_prior_state() -> None:
    ledger = ReplayObligationLedger()
    validation = {
        "status": "fail",
        "phase": "candidate-validation",
        "candidate_validation": {
            "policy_id": "minimal",
            "reason": "invalid candidate",
            "details": {},
        },
    }
    unknown = {
        "status": "infrastructure_error",
        "phase": "clean-replay",
        "verification": {
            "obligation_snapshot": {
                "schema": REPLAY_OBLIGATION_SNAPSHOT_SCHEMA,
                "coverage": "unknown",
                "verification_passed": None,
                "finding_set_complete": False,
                "obligations": [],
            }
        },
    }

    introduced = ledger.update(validation)
    preserved = ledger.update(unknown)

    assert introduced["active_obligation_count"] == 1
    assert preserved["active_obligation_count"] == 1
    assert preserved["delta"]["preserved_unobserved"]["count"] == 1
    assert preserved["update_semantics"] == "preserve-under-partial-observability"
