from __future__ import annotations

import tempfile
from pathlib import Path

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.codex.matched_replay_mcp import (
    WithheldReplayService,
    matched_envbench_replay_payload,
    matched_replay_payload,
)
from envsolve_harness.core.io import read_json, read_jsonl
from envsolve_harness.core.models import Case
from envsolve_harness.runners.matched_official_replay import (
    RemoteOfficialPathMatchedReplayRealRunner,
    RemoteOfficialPathMatchedReplayWithheldRunner,
)
from envsolve_harness.runners.matched_replay import (
    RemoteBoundaryV6MatchedReplayRealRunner,
    RemoteBoundaryV6MatchedReplayWithheldRunner,
    RemoteBoundaryV6MatchedTargetStateReplayRealRunner,
    RemoteBoundaryV6MatchedTargetStateReplayWithheldRunner,
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


def test_withheld_replay_can_match_envbench_identifiers() -> None:
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
            replay_id_prefix="envbench-replay",
            phase="target-state-replay",
        )

        result = service.submit("true")

        assert result["replay_id"] == "envbench-replay-0001"
        assert result["phase"] == "target-state-replay"


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


def test_target_state_matched_arms_share_prompt_and_only_real_feedback() -> None:
    assert (
        RemoteBoundaryV6MatchedTargetStateReplayRealRunner._prompt
        is RemoteBoundaryV6MatchedTargetStateReplayWithheldRunner._prompt
    )
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        runner = RemoteBoundaryV6MatchedTargetStateReplayRealRunner(
            ssh_target="user@spark",
            remote_workspace_root="/srv/construction",
            codex_executable=root / "codex",
            harness_root=root,
            source_cache_root=root / "cache",
            image="envbench:test",
            timeout=120,
            command_timeout=30,
            container_create_timeout=10,
            git_fetch_timeout=20,
            goal_contract=ExecutableGoalContract("goal", "Fixture", "true"),
        )
        arguments = runner._mcp_server_args(
            trace_path=root / "trace.jsonl",
            container_id="construction",
            case=Case("owner/repo@abc", "owner/repo", "abc"),
            image_digest="sha256:image",
        )

    assert arguments[-5:] == [
        "--feedback-mode",
        "real",
        "--preserve-bind-mount-owner",
        "--replay-container-workdir",
        "/data/project",
    ]


def test_envbench_real_and_withheld_feedback_have_identical_shape() -> None:
    real = matched_envbench_replay_payload(
        {
            "replay_id": "real-1",
            "replay_index": 1,
            "program_sha256": "abc",
            "program_artifact": "programs/real-1.sh",
            "status": "fail",
            "phase": "target-state-replay",
            "candidate_validation": {"accepted": True},
            "feedback": {
                "schema_version": "1.0.0",
                "status": "completed",
                "withheld": False,
                "bootstrap": {
                    "terminal_class": "bootstrap_failed",
                    "exit_code": 1,
                    "git_ownership_error": True,
                },
                "goal_report": {
                    "present": False,
                    "issues_count": 0,
                    "error_count": None,
                },
                "missing_imports": [],
                "active_project_python": None,
                "infrastructure": None,
            },
            "certified": False,
        }
    )
    withheld = matched_envbench_replay_payload(
        {
            "replay_id": "withheld-1",
            "replay_index": 1,
            "program_sha256": "abc",
            "program_artifact": "programs/withheld-1.sh",
            "status": "withheld",
            "phase": "target-state-replay",
            "candidate_validation": {"accepted": True},
            "certified": False,
        }
    )

    assert list(real) == list(withheld)
    assert list(real["feedback"]) == list(withheld["feedback"])
    assert list(real["feedback"]["bootstrap"]) == list(
        withheld["feedback"]["bootstrap"]
    )
    assert real["feedback"]["bootstrap"]["git_ownership_error"] is True
    assert withheld["feedback"]["bootstrap"]["git_ownership_error"] is None
    assert real["withheld"] is False
    assert withheld["withheld"] is True


def test_official_path_matched_arms_share_prompt_and_executor(tmp_path: Path) -> None:
    common = {
        "ssh_target": "user@spark",
        "remote_workspace_root": "/srv/construction",
        "codex_executable": tmp_path / "codex",
        "harness_root": tmp_path,
        "source_cache_root": tmp_path / "cache",
        "image": "envbench:test",
        "timeout": 120,
        "command_timeout": 30,
        "container_create_timeout": 10,
        "git_fetch_timeout": 20,
        "goal_contract": ExecutableGoalContract("goal", "Fixture", "true"),
        "local_envbench_root": tmp_path / "EnvBench",
        "remote_envbench_root": "/srv/EnvBench",
        "remote_evaluation_root": "/srv/evaluation",
        "evaluation_process_timeout": 600,
        "evaluation_container_timeout": 500,
        "evaluation_max_workers": 1,
    }
    control = RemoteOfficialPathMatchedReplayWithheldRunner(**common)
    treatment = RemoteOfficialPathMatchedReplayRealRunner(**common)
    case = Case("owner/repo@abc", "owner/repo", "abc")
    control_prompt = control._prompt(case, control.goal_contract)
    treatment_prompt = treatment._prompt(case, treatment.goal_contract)
    control_args = control._mcp_server_args(
        trace_path=tmp_path / "control" / "trace.jsonl",
        container_id="control",
        case=case,
        image_digest="sha256:image",
    )
    treatment_args = treatment._mcp_server_args(
        trace_path=tmp_path / "treatment" / "trace.jsonl",
        container_id="treatment",
        case=case,
        image_digest="sha256:image",
    )

    assert control_prompt == treatment_prompt
    assert "envsolve_harness.codex.envbench_replay_mcp" in control_args
    assert "envsolve_harness.codex.envbench_replay_mcp" in treatment_args
    assert control_args[-2:] == ["--feedback-mode", "withheld"]
    assert treatment_args[-2:] == ["--feedback-mode", "real"]
