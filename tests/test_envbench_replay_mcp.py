from __future__ import annotations

from pathlib import Path

from envsolve.runtime.goal import ExecutableGoalContract
from envsolve_harness.adapters.envbench_executor import EnvBenchCandidateExecution
from envsolve_harness.codex.envbench_replay_mcp import (
    EXECUTOR_PROFILE,
    EnvBenchReplayService,
)
from envsolve_harness.core.io import read_json, read_jsonl
from envsolve_harness.core.models import Case
from envsolve_harness.runners.official_path_replay import (
    RemoteOfficialPathMinimalBRunner,
)
from envsolve_harness.runners.remote_boundary_v6 import (
    OfficialPrimaryRemoteBoundaryV6CodexCliRunner,
)
from experiments.run_envsolve_pro_m1c_branches import continuation_prompt


def _execution(
    root: Path,
    *,
    exit_code: int = 0,
    issues_count: int = 0,
) -> EnvBenchCandidateExecution:
    return EnvBenchCandidateExecution(
        command=("uv", "run", "python", "evaluation/main.py"),
        process_returncode=0,
        stdout="",
        stderr="",
        raw={
            "repo_name": "owner/repo",
            "commit_sha": "a" * 40,
            "exit_code": exit_code,
            "issues_count": issues_count,
            "container_logs": "Using Python 3.12 located at /data/project/.venv/bin/python\n",
            "pyright": {
                "summary": {"errorCount": issues_count},
                "generalDiagnostics": [],
            },
        },
        result_path=root / "results.jsonl",
        repository_acquisition=None,
        adapter_error=None,
        termination=None,
        identity_matches=True,
        diagnostic_integrity_valid=True,
        completed=True,
        started_at="start",
        finished_at="finish",
    )


def test_envbench_replay_certifies_only_official_goal_pass(tmp_path: Path) -> None:
    observed: list[tuple[str, str]] = []

    def execute(
        program: str, replay_id: str
    ) -> tuple[EnvBenchCandidateExecution, dict[str, str]]:
        observed.append((program, replay_id))
        return _execution(tmp_path), {"kind": "fixture-envbench"}

    service = EnvBenchReplayService(
        case=Case("case", "owner/repo", "a" * 40),
        image_digest="sha256:image",
        goal_contract_sha256="goal-digest",
        trace_path=tmp_path / "replays.jsonl",
        certification_path=tmp_path / "certification.json",
        programs_root=tmp_path / "programs",
        execute_candidate=execute,
    )

    result = service.submit("true\n")

    assert result["status"] == "pass"
    assert result["certified"] is True
    assert result["executor_profile"] == EXECUTOR_PROFILE
    assert result["feedback"]["goal_report"]["issues_count"] == 0
    assert observed == [("true", "envbench-replay-0001")]
    trace = read_jsonl(tmp_path / "replays.jsonl")
    assert trace[0]["program_sha256"] == result["program_sha256"]
    certification = read_json(tmp_path / "certification.json")
    assert certification["certified_programs"][0]["environment_receipt"] == {
        "environment_id": "envbench-replay-0001",
        "repository": "owner/repo",
        "revision": "a" * 40,
        "image_digest": "sha256:image",
        "executor_profile": EXECUTOR_PROFILE,
    }


def test_envbench_replay_returns_failed_target_observation_without_certificate(
    tmp_path: Path,
) -> None:
    service = EnvBenchReplayService(
        case=Case("case", "owner/repo", "a" * 40),
        image_digest="sha256:image",
        goal_contract_sha256="goal-digest",
        trace_path=tmp_path / "replays.jsonl",
        certification_path=tmp_path / "certification.json",
        programs_root=tmp_path / "programs",
        execute_candidate=lambda program, replay_id: (
            _execution(tmp_path, issues_count=3),
            {"kind": "fixture-envbench"},
        ),
    )

    result = service.submit("python -m pip install -e .")

    assert result["status"] == "fail"
    assert result["certified"] is False
    assert result["feedback"]["goal_report"]["issues_count"] == 3
    assert read_json(tmp_path / "certification.json")["certified_programs"] == []


def _runner(root: Path, runner_type: type):
    kwargs = {
        "ssh_target": "user@spark",
        "remote_workspace_root": "/srv/construction",
        "codex_executable": root / "codex",
        "harness_root": root,
        "source_cache_root": root / "cache",
        "image": "envbench:test",
        "timeout": 120,
        "command_timeout": 30,
        "container_create_timeout": 10,
        "git_fetch_timeout": 20,
        "goal_contract": ExecutableGoalContract("goal", "Fixture", "true"),
    }
    if runner_type is RemoteOfficialPathMinimalBRunner:
        kwargs.update(
            {
                "local_envbench_root": root / "EnvBench",
                "remote_envbench_root": "/srv/EnvBench",
                "remote_evaluation_root": "/srv/evaluation",
                "evaluation_process_timeout": 600,
                "evaluation_container_timeout": 500,
                "evaluation_max_workers": 1,
            }
        )
    return runner_type(**kwargs)


def test_official_path_b_differs_from_a_only_by_replay_interface(
    tmp_path: Path,
) -> None:
    case = Case("case", "owner/repo", "a" * 40)
    control = _runner(tmp_path, OfficialPrimaryRemoteBoundaryV6CodexCliRunner)
    treatment = _runner(tmp_path, RemoteOfficialPathMinimalBRunner)

    control_prompt = control._prompt(case, control.goal_contract)
    treatment_prompt = treatment._prompt(case, treatment.goal_contract)
    arguments = treatment._mcp_server_args(
        trace_path=tmp_path / "trace.jsonl",
        container_id="container",
        case=case,
        image_digest="sha256:image",
    )

    assert treatment_prompt.startswith(control_prompt)
    suffix = treatment_prompt[len(control_prompt) :]
    assert "submit_and_replay" in suffix
    assert "same EnvBench candidate-execution path" in suffix
    assert "envsolve_harness.codex.envbench_replay_mcp" in arguments
    assert "/srv/EnvBench" in arguments
    assert "/srv/evaluation" in arguments
    assert treatment._mcp_tool_names() == ("envbench_shell", "submit_and_replay")


def test_m1c_c1_and_t_prompts_have_identical_structure() -> None:
    real = {
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
    }
    null = {
        "schema_version": "1.0.0",
        "status": "withheld",
        "withheld": True,
        "bootstrap": {
            "terminal_class": None,
            "exit_code": None,
            "git_ownership_error": None,
        },
        "goal_report": {
            "present": None,
            "issues_count": None,
            "error_count": None,
        },
        "missing_imports": None,
        "active_project_python": None,
        "infrastructure": None,
    }

    real_prompt = continuation_prompt(real)
    null_prompt = continuation_prompt(null)

    assert real_prompt.split("{", 1)[0] == null_prompt.split("{", 1)[0]
    assert real_prompt.rsplit("}", 1)[1] == null_prompt.rsplit("}", 1)[1]
    assert "additional revision opportunity" in real_prompt
