from __future__ import annotations

from pathlib import Path
import tempfile

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.codex.matched_replay_mcp import (
    WithheldReplayService,
    matched_replay_payload,
)
from envsolve_harness.core.io import read_json, read_jsonl
from envsolve_harness.core.models import Case
from envsolve_harness.runners.matched_replay import (
    RemoteBoundaryV6MatchedReplayRealRunner,
    RemoteBoundaryV6MatchedReplayWithheldRunner,
)


def test_withheld_replay_records_candidate_without_executing_target() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        service = WithheldReplayService(
            repository="owner/repo",
            revision="abc",
            image_digest="sha256:image",
            goal_contract_sha256="goal",
            trace_path=root / "replays.jsonl",
            certification_path=root / "certification.json",
            programs_root=root / "programs",
        )

        result = service.submit("#!/bin/sh\ntrue\n")

        assert result["status"] == "withheld"
        assert result["candidate_validation"]["accepted"] is True
        assert read_jsonl(root / "replays.jsonl")[0]["status"] == "withheld"
        certification = read_json(root / "certification.json")
        assert certification["replay_count"] == 1
        assert certification["certified_programs"] == []
        assert (root / "programs" / "minimal-b-replay-0001.sh").is_file()


def test_real_and_withheld_feedback_use_the_same_projected_fields() -> None:
    real = matched_replay_payload(
        {
            "replay_id": "real-1",
            "replay_index": 1,
            "program_sha256": "abc",
            "program_artifact": "programs/real-1.sh",
            "status": "fail",
            "phase": "clean-replay",
            "candidate_validation": {"accepted": True},
            "environment_receipt": {"environment_id": "fresh"},
            "verification": {
                "verifier": "public-goal",
                "check_profile": "goal-v1",
                "feedback_channel": "internal_execution",
                "passed": False,
                "summary": "bootstrap failed",
                "bootstrap": {
                    "exit_code": 1,
                    "stdout": "",
                    "stdout_truncated": False,
                    "stderr": "failure",
                    "stderr_truncated": False,
                    "duration_seconds": 1.0,
                },
                "observations": {"json": "[]", "truncated": False},
                "counterexamples": {"json": "[]", "truncated": False},
                "details": {"json": "{}", "truncated": False},
            },
            "certified": False,
        }
    )
    withheld = matched_replay_payload(
        {
            "replay_id": "null-1",
            "replay_index": 1,
            "program_sha256": "abc",
            "program_artifact": "programs/null-1.sh",
            "status": "withheld",
            "phase": "clean-replay",
            "candidate_validation": {"accepted": True},
            "certified": False,
        }
    )

    assert list(real) == list(withheld)
    assert list(real["verification"]) == list(withheld["verification"])
    assert list(real["verification"]["bootstrap"]) == list(
        withheld["verification"]["bootstrap"]
    )
    assert real["withheld"] is False
    assert withheld["withheld"] is True


def test_matched_arms_inherit_one_agent_visible_prompt_implementation() -> None:
    assert (
        RemoteBoundaryV6MatchedReplayRealRunner._prompt
        is RemoteBoundaryV6MatchedReplayWithheldRunner._prompt
    )


def test_matched_prompt_does_not_include_the_legacy_pass_gate() -> None:
    runner = object.__new__(RemoteBoundaryV6MatchedReplayWithheldRunner)
    prompt = runner._prompt(
        Case("owner/repo@abc", "owner/repo", "abc"),
        ExecutableGoalContract(
            contract_id="goal",
            description="goal",
            program="true",
        ),
    )

    assert "frozen EnvSolve-Pro Minimal B interface" not in prompt
    assert "only after the exact same program receives" not in prompt
    assert "If `status=withheld`" in prompt
