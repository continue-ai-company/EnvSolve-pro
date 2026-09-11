from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

from envsolve_harness.adapters.envbench_executor import (
    EnvBenchCandidateExecutor,
    EnvBenchCandidateRequest,
    envbench_feedback_payload,
    withheld_envbench_feedback_payload,
)
from envsolve_harness.core.io import write_jsonl
from envsolve_harness.core.models import Case


class _UnusedSourceCache:
    def __init__(self, root: Path, timeout: int) -> None:
        raise AssertionError((root, timeout))


def _request(root: Path, name: str) -> EnvBenchCandidateRequest:
    execution = root / name
    return EnvBenchCandidateRequest(
        case=Case("owner/repo@abc", "owner/repo", "abc"),
        script="true\n",
        benchmark_root=root / "EnvBench",
        benchmark_input=execution / "input.jsonl",
        json_results=execution / "json",
        repo_data=execution / "repos",
        temp_dir=execution / "tmp",
        image="envbench:test",
        source_cache_root=None,
        max_workers=1,
        process_timeout=60,
        create_container_timeout=30,
        container_timeout=45,
        git_fetch_timeout=20,
        cleanup_root=execution,
    )


def _schema_shape(value: object) -> object:
    if isinstance(value, dict):
        return [(key, _schema_shape(child)) for key, child in value.items()]
    return "scalar"


def test_online_and_postepisode_modes_share_candidate_execution_observables() -> None:
    calls: list[list[str]] = []

    def execute(
        command: list[str],
        *,
        cwd: Path,
        timeout: int,
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[str]:
        del cwd, timeout, env
        calls.append(command)
        output = next(
            Path(item.split("=", 1)[1])
            for item in command
            if item.startswith("operation.dirs.json_results=")
        )
        write_jsonl(
            output / "results.jsonl",
            [
                {
                    "repo_name": "owner/repo",
                    "commit_sha": "abc",
                    "exit_code": 0,
                    "issues_count": 1,
                    "container_logs": (
                        "Using Python 3.12.0 located at "
                        "/data/project/venv/bin/python\n"
                    ),
                    "pyright": {
                        "summary": {"errorCount": 1, "warningCount": 0},
                        "generalDiagnostics": [
                            {
                                "file": "/data/project/src/main.py",
                                "rule": "reportMissingImports",
                                "message": 'Import "missing_pkg" could not be resolved',
                            }
                        ],
                    },
                }
            ],
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        executor = EnvBenchCandidateExecutor(
            execute,
            _UnusedSourceCache,
            lambda path: (),
        )
        online = executor.execute(_request(root, "online"))
        postepisode = executor.execute(_request(root, "postepisode"))

    assert len(calls) == 2
    assert envbench_feedback_payload(online) == envbench_feedback_payload(postepisode)
    assert envbench_feedback_payload(online)["missing_imports"] == [
        {"path": "src/main.py", "module": "missing_pkg", "count": 1}
    ]
    assert envbench_feedback_payload(online)["active_project_python"] == (
        "venv/bin/python"
    )


def test_null_feedback_has_same_ordered_schema_as_real_feedback() -> None:
    execution = type(
        "ExecutionFixture",
        (),
        {
            "raw": {},
            "completed": False,
            "termination": None,
        },
    )()

    real = envbench_feedback_payload(execution)
    withheld = withheld_envbench_feedback_payload()

    assert _schema_shape(real) == _schema_shape(withheld)
    assert withheld["status"] == "withheld"
    assert withheld["withheld"] is True


def test_source_cache_preseeds_official_repository_directory() -> None:
    acquisitions: list[dict[str, object]] = []

    class RecordingSourceCache:
        def __init__(self, root: Path, timeout: int) -> None:
            acquisitions.append({"root": root, "timeout": timeout})

        def acquire(
            self,
            *,
            repository: str,
            revision: str,
            destination: Path,
        ) -> dict[str, object]:
            destination.mkdir(parents=True)
            acquisitions.append(
                {
                    "repository": repository,
                    "revision": revision,
                    "destination": destination,
                }
            )
            return {"source": "test-cache", "commit": revision}

    def execute(
        command: list[str],
        *,
        cwd: Path,
        timeout: int,
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[str]:
        del cwd, timeout, env
        output = next(
            Path(item.split("=", 1)[1])
            for item in command
            if item.startswith("operation.dirs.json_results=")
        )
        write_jsonl(
            output / "results.jsonl",
            [
                {
                    "repo_name": "owner/repo",
                    "commit_sha": "abc",
                    "exit_code": 0,
                    "issues_count": 0,
                    "pyright": {"summary": {"errorCount": 0}},
                }
            ],
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        request = _request(root, "cached")
        request = EnvBenchCandidateRequest(
            **{
                **request.__dict__,
                "source_cache_root": root / "source-cache",
            }
        )
        result = EnvBenchCandidateExecutor(
            execute,
            RecordingSourceCache,
            lambda path: (),
        ).execute(request)

    assert result.completed is True
    assert acquisitions == [
        {"root": root / "source-cache", "timeout": 20},
        {
            "repository": "owner/repo",
            "revision": "abc",
            "destination": root / "cached" / "repos" / "owner__repo@abc",
        },
    ]
    assert result.repository_acquisition == {
        "source": "test-cache",
        "commit": "abc",
    }
