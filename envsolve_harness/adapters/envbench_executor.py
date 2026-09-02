from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
import os
import re
import subprocess
from typing import Any, Callable, Protocol

from envsolve_harness.adapters.infrastructure import (
    envbench_bootstrap_infrastructure_signature,
)
from envsolve_harness.core.io import read_jsonl, write_jsonl
from envsolve_harness.core.models import Case


class ProcessRunner(Protocol):
    def __call__(
        self,
        command: list[str],
        *,
        cwd: Path,
        timeout: int,
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[str]: ...


class SourceCache(Protocol):
    def acquire(
        self,
        *,
        repository: str,
        revision: str,
        destination: Path,
        remote_url: str | None = None,
    ) -> dict[str, Any]: ...


SourceCacheFactory = Callable[[Path, int], SourceCache]
ContainerCleanup = Callable[[Path], tuple[str, ...]]

_MISSING_IMPORT = re.compile(r'Import "([^"]+)" could not be resolved')
_ACTIVE_PYTHON = re.compile(r"Using Python [^\n]* located at ([^\n]+)")


@dataclass(frozen=True)
class EnvBenchCandidateRequest:
    case: Case
    script: str
    benchmark_root: Path
    benchmark_input: Path
    json_results: Path
    repo_data: Path
    temp_dir: Path
    image: str
    source_cache_root: Path | None
    max_workers: int
    process_timeout: int
    create_container_timeout: int
    container_timeout: int
    git_fetch_timeout: int
    cleanup_root: Path


@dataclass(frozen=True)
class EnvBenchCandidateExecution:
    command: tuple[str, ...]
    process_returncode: int | None
    stdout: str
    stderr: str
    raw: dict[str, Any]
    result_path: Path
    repository_acquisition: dict[str, Any] | None
    adapter_error: str | None
    termination: dict[str, Any] | None
    identity_matches: bool
    diagnostic_integrity_valid: bool
    completed: bool
    started_at: str
    finished_at: str


def _project_relative(value: str) -> str:
    prefix = "/data/project/"
    if value.startswith(prefix):
        return value[len(prefix) :]
    if value == "/data/project":
        return "."
    return value


def envbench_feedback_payload(
    execution: EnvBenchCandidateExecution,
) -> dict[str, Any]:
    """Serialize only candidate-execution observations exposed to the F branch."""

    raw = execution.raw
    pyright = raw.get("pyright") if isinstance(raw.get("pyright"), dict) else {}
    summary = pyright.get("summary") if isinstance(pyright.get("summary"), dict) else {}
    diagnostics = pyright.get("generalDiagnostics")
    if not isinstance(diagnostics, list):
        diagnostics = []
    missing = Counter(
        (
            _project_relative(str(item.get("file", ""))),
            match.group(1),
        )
        for item in diagnostics
        if isinstance(item, dict) and item.get("rule") == "reportMissingImports"
        for match in [_MISSING_IMPORT.search(str(item.get("message", "")))]
        if match is not None
    )
    logs = raw.get("container_logs")
    python_match = _ACTIVE_PYTHON.search(logs) if isinstance(logs, str) else None
    exit_code = raw.get("exit_code")
    if execution.completed:
        terminal_class = "bootstrap_completed" if exit_code == 0 else "bootstrap_failed"
        status = "completed"
    elif (
        isinstance(execution.termination, dict)
        and execution.termination.get("kind") == "infrastructure_unknown"
    ):
        terminal_class = "infrastructure_censored"
        status = "censored"
    else:
        terminal_class = "execution_incomplete"
        status = "incomplete"
    return {
        "schema_version": "1.0.0",
        "status": status,
        "withheld": False,
        "bootstrap": {
            "terminal_class": terminal_class,
            "exit_code": exit_code,
            "git_ownership_error": (
                "detected dubious ownership" in logs.lower()
                if isinstance(logs, str)
                else False
            ),
        },
        "goal_report": {
            "present": isinstance(summary.get("errorCount"), int),
            "issues_count": raw.get("issues_count"),
            "error_count": summary.get("errorCount"),
        },
        "missing_imports": [
            {"path": path, "module": module, "count": count}
            for (path, module), count in sorted(missing.items())
        ],
        "active_project_python": (
            _project_relative(python_match.group(1).strip())
            if python_match is not None
            else None
        ),
        "infrastructure": execution.termination,
    }


def withheld_envbench_feedback_payload() -> dict[str, Any]:
    """Return the N branch payload with the same schema and no measured result."""

    return {
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


def _timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value


class EnvBenchCandidateExecutor:
    """Execute one candidate through the exact EnvBench evaluator path."""

    def __init__(
        self,
        process_runner: ProcessRunner,
        source_cache_factory: SourceCacheFactory,
        cleanup_containers: ContainerCleanup,
    ) -> None:
        self._process_runner = process_runner
        self._source_cache_factory = source_cache_factory
        self._cleanup_containers = cleanup_containers

    def execute(self, request: EnvBenchCandidateRequest) -> EnvBenchCandidateExecution:
        request.benchmark_input.parent.mkdir(parents=True, exist_ok=True)
        request.json_results.mkdir(parents=True, exist_ok=True)
        request.repo_data.mkdir(parents=True, exist_ok=True)
        request.temp_dir.mkdir(parents=True, exist_ok=True)
        write_jsonl(
            request.benchmark_input,
            [
                {
                    "repository": request.case.repository,
                    "revision": request.case.revision,
                    "script": request.script,
                }
            ],
        )

        repository_acquisition: dict[str, Any] | None = None
        repository_acquisition_error: str | None = None
        if request.source_cache_root is not None:
            destination = (
                request.repo_data
                / f"{request.case.repository.replace('/', '__')}@{request.case.revision}"
            )
            try:
                repository_acquisition = self._source_cache_factory(
                    request.source_cache_root,
                    request.git_fetch_timeout,
                ).acquire(
                    repository=request.case.repository,
                    revision=request.case.revision,
                    destination=destination,
                )
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                repository_acquisition_error = (
                    "Official repository cache acquisition failed: "
                    f"{type(exc).__name__}: {exc}"
                )

        command = (
            "uv",
            "run",
            "python",
            "evaluation/main.py",
            "language=python",
            "input.mode=local",
            f"input.local={request.benchmark_input}",
            "input.use_scripts=true",
            "output.mode=local",
            f"operation.dirs.repo_data={request.repo_data}",
            f"operation.dirs.json_results={request.json_results}",
            f"operation.dirs.tmp={request.temp_dir}",
            "+operation.rewrite_results=true",
            f"operation.pool_config.max_workers={request.max_workers}",
            "operation.pool_config.chunksize=1",
            f"docker.container_timeout={request.container_timeout}",
            f"docker.create_container_timeout={request.create_container_timeout}",
            f"docker.image.python={request.image}",
        )
        started_at = datetime.now(timezone.utc).isoformat()
        process_returncode: int | None = None
        stdout = ""
        stderr = ""
        adapter_error: str | None = None
        termination: dict[str, Any] | None = None
        if repository_acquisition_error is not None:
            adapter_error = repository_acquisition_error
            termination = {
                "kind": "infrastructure_unknown",
                "scope": "evaluator_repository_acquisition",
                "signature": "source-cache-acquisition-failed",
            }
            stderr = adapter_error
        else:
            try:
                process_env = os.environ.copy()
                process_env["ENVBENCH_GIT_FETCH_TIMEOUT_SECONDS"] = str(
                    request.git_fetch_timeout
                )
                process = self._process_runner(
                    list(command),
                    cwd=request.benchmark_root,
                    timeout=request.process_timeout,
                    env=process_env,
                )
                process_returncode = process.returncode
                stdout = process.stdout
                stderr = process.stderr
            except subprocess.TimeoutExpired as exc:
                stdout = _timeout_output(exc.stdout)
                stderr = _timeout_output(exc.stderr)
                adapter_error = (
                    "Evaluation process exceeded hard budget "
                    f"of {request.process_timeout} seconds"
                )
                cleaned_container_ids = self._cleanup_containers(request.cleanup_root)
                termination = {
                    "kind": "budget_exhausted",
                    "scope": "evaluation_process",
                    "limit_seconds": request.process_timeout,
                    "cleaned_container_ids": list(cleaned_container_ids),
                }
                stderr = f"{stderr}\n{adapter_error}".strip()
            except OSError as exc:
                adapter_error = f"{type(exc).__name__}: {exc}"
                stderr = adapter_error

        result_path = request.json_results / "results.jsonl"
        raw: dict[str, Any] = {}
        if result_path.exists():
            records = read_jsonl(result_path)
            if len(records) == 1:
                raw = records[0]

        identity_matches = (
            raw.get("repo_name") == request.case.repository
            and raw.get("commit_sha") == request.case.revision
        )
        infrastructure_signature = (
            envbench_bootstrap_infrastructure_signature(raw)
            if process_returncode == 0 and bool(raw) and identity_matches
            else None
        )
        if infrastructure_signature is not None:
            adapter_error = (
                "EnvBench bootstrap was censored by infrastructure failure: "
                f"{infrastructure_signature}"
            )
            termination = {
                "kind": "infrastructure_unknown",
                "scope": "evaluator_bootstrap",
                "signature": infrastructure_signature,
            }
        pyright = raw.get("pyright")
        summary = pyright.get("summary") if isinstance(pyright, dict) else None
        if not isinstance(summary, dict):
            summary = {}
        exit_code = raw.get("exit_code")
        diagnostic_integrity_valid = not (
            exit_code == 0 and not isinstance(summary.get("errorCount"), int)
        )
        if (
            process_returncode == 0
            and bool(raw)
            and identity_matches
            and infrastructure_signature is None
            and not diagnostic_integrity_valid
        ):
            adapter_error = (
                "EnvBench returned a successful bootstrap without valid Pyright diagnostics"
            )
            termination = {
                "kind": "measurement_integrity_unknown",
                "scope": "evaluator_diagnostics",
                "signature": "missing-pyright-summary",
            }
        completed = (
            process_returncode == 0
            and bool(raw)
            and identity_matches
            and infrastructure_signature is None
            and diagnostic_integrity_valid
        )
        return EnvBenchCandidateExecution(
            command=command,
            process_returncode=process_returncode,
            stdout=stdout,
            stderr=stderr,
            raw=raw,
            result_path=result_path,
            repository_acquisition=repository_acquisition,
            adapter_error=adapter_error,
            termination=termination,
            identity_matches=identity_matches,
            diagnostic_integrity_valid=diagnostic_integrity_valid,
            completed=completed,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
