from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

from envsolve_harness.core.io import write_json, write_text_atomic
from envsolve_harness.core.models import (
    Case,
    EvaluationResult,
    HarnessConfig,
    RunSpec,
    VerificationEvidence,
)
from envsolve_harness.core.protocol import ExperimentProtocol
from envsolve_harness.adapters.envbench_diagnostics import (
    build_envbench_diagnostic_evidence,
)
from envsolve_harness.adapters.envbench_executor import (
    EnvBenchCandidateExecutor,
    EnvBenchCandidateRequest,
)
from envsolve_harness.adapters.envbench_goal import envbench_python_goal_contract
from envsolve_harness.adapters.envbench_remote import RemoteEnvBenchProcessRunner
from envsolve_harness.execution.batch import cleanup_case_containers
from envsolve_harness.execution.remote_docker import SshDockerTransport
from envsolve_harness.execution.source_cache import ExactRevisionSourceCache
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import ensure_manifest, update_manifest
from envsolve_harness.utils.provenance import (
    docker_image_provenance,
    git_provenance,
    sha256_file,
)
from envsolve.runtime.workspace import WorkspacePrecondition
from envsolve.runtime.goal import ExecutableGoalContract


def _run_envbench_process(
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError as exc:
        local_uv = cwd / ".venv/bin/uv"
        if exc.filename != "uv" or not local_uv.is_file():
            raise
        command[0] = str(local_uv)
        return subprocess.run(
            list(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=env,
        )


class EnvBenchEvaluator:
    def __init__(self, config: HarnessConfig, protocol: ExperimentProtocol) -> None:
        self.config = config
        self.protocol = protocol
        self.benchmark = config.benchmark(protocol.benchmark)
        if self.benchmark.adapter != "envbench":
            raise ValueError(
                f"EnvBenchEvaluator cannot execute adapter {self.benchmark.adapter!r}"
            )
        image = self.benchmark.settings.get("image")
        if not isinstance(image, str) or not image:
            raise ValueError("EnvBench benchmark settings require a non-empty image")
        self.image = image
        preseed_source_cache = self.benchmark.settings.get(
            "preseed_source_cache", False
        )
        if not isinstance(preseed_source_cache, bool):
            raise ValueError(
                "EnvBench preseed_source_cache setting must be a boolean"
            )
        self.preseed_source_cache = preseed_source_cache
        execution_backend = self.benchmark.settings.get(
            "execution_backend", "local"
        )
        if execution_backend not in {"local", "ssh-remote-envbench"}:
            raise ValueError(
                "EnvBench execution_backend must be local or ssh-remote-envbench"
            )
        self.execution_backend = execution_backend
        self.remote_benchmark_root: str | None = None
        self.remote_workspace_root: str | None = None
        if execution_backend == "ssh-remote-envbench":
            remote_benchmark_root = self.benchmark.settings.get(
                "remote_benchmark_root"
            )
            remote_workspace_root = self.benchmark.settings.get(
                "remote_workspace_root"
            )
            if not isinstance(remote_benchmark_root, str) or not remote_benchmark_root:
                raise ValueError(
                    "Remote EnvBench execution requires remote_benchmark_root"
                )
            if not isinstance(remote_workspace_root, str) or not remote_workspace_root:
                raise ValueError(
                    "Remote EnvBench execution requires remote_workspace_root"
                )
            self.remote_benchmark_root = remote_benchmark_root
            self.remote_workspace_root = remote_workspace_root

    @staticmethod
    def _optional_remote_port() -> int | None:
        value = os.environ.get("ENVSOLVE_REMOTE_SSH_PORT", "").strip()
        if not value:
            return None
        port = int(value)
        if not 1 <= port <= 65535:
            raise ValueError("ENVSOLVE_REMOTE_SSH_PORT must be between 1 and 65535")
        return port

    def _remote_process_runner(
        self,
        *,
        artifacts: RunArtifacts,
        benchmark_input: Path,
        json_results: Path,
        repo_data: Path,
        temp_dir: Path,
    ) -> RemoteEnvBenchProcessRunner:
        target = os.environ.get("ENVSOLVE_REMOTE_DOCKER_TARGET", "").strip()
        if not target:
            raise ValueError(
                "Remote EnvBench execution requires ENVSOLVE_REMOTE_DOCKER_TARGET"
            )
        if self.remote_benchmark_root is None or self.remote_workspace_root is None:
            raise RuntimeError("Remote EnvBench paths were not configured")
        transport = SshDockerTransport(
            target=target,
            remote_root=self.remote_workspace_root,
            ssh_executable=shutil.which("ssh") or "ssh",
            rsync_executable=shutil.which("rsync") or "rsync",
            docker_executable=(
                os.environ.get("ENVSOLVE_REMOTE_DOCKER_EXECUTABLE", "").strip()
                or "docker"
            ),
            ssh_identity=(
                os.environ.get("ENVSOLVE_REMOTE_SSH_IDENTITY", "").strip() or None
            ),
            ssh_port=self._optional_remote_port(),
        )
        return RemoteEnvBenchProcessRunner(
            transport=transport,
            local_benchmark_root=self.benchmark.root,
            remote_benchmark_root=self.remote_benchmark_root,
            local_benchmark_input=benchmark_input,
            local_json_results=json_results,
            local_repo_data=repo_data,
            local_temp_dir=temp_dir,
            remote_run_root=transport.workspace_path(artifacts.root, "official"),
            image=self.image,
            sync_timeout=max(
                self.config.git_fetch_timeout,
                self.config.create_container_timeout,
            ),
        )

    @property
    def benchmark_id(self) -> str:
        return self.benchmark.benchmark_id

    @property
    def workspace_preconditions(self) -> tuple[WorkspacePrecondition, ...]:
        return (
            WorkspacePrecondition(
                "build_output",
                producer="envbench-python-build-v1",
            ),
        )

    @property
    def goal_contract(self) -> ExecutableGoalContract:
        return envbench_python_goal_contract()

    def evaluate(
        self,
        case: Case,
        script_path: Path,
        artifacts: RunArtifacts,
        run_spec: RunSpec,
    ) -> EvaluationResult:
        if case.language != self.protocol.language:
            raise ValueError(
                f"Case language {case.language!r} does not match protocol language {self.protocol.language!r}"
            )
        if case.language != "python":
            raise ValueError("P0 EnvBench adapter currently supports Python cases only")
        manifest = ensure_manifest(artifacts, self.config, case, run_spec, self.protocol)
        if manifest.get("evaluator") is not None or manifest.get("result") is not None:
            raise RuntimeError("Official evaluation has already been recorded for this run")
        claim = {
            "schema_version": "1.0.0",
            "channel": "official",
            "benchmark": self.benchmark_id,
            "run_id": run_spec.run_id,
            "case_id": case.case_id,
            "claimed_at": datetime.now(timezone.utc).isoformat(),
        }
        artifacts.evaluation_claim.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(
                artifacts.evaluation_claim,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError as exc:
            raise RuntimeError(
                "Official evaluation has already been attempted for this run"
            ) from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(claim, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        script = script_path.read_text(encoding="utf-8")
        write_json(
            artifacts.status,
            {"state": "preparing", "updated_at": datetime.now(timezone.utc).isoformat()},
        )
        write_text_atomic(artifacts.bootstrap_script, script)
        write_json(artifacts.case_input, case.to_dict())
        json_results = artifacts.evaluation_dir / "json"
        repo_data = artifacts.evaluation_dir / "repos"
        temp_dir = artifacts.evaluation_dir / "tmp"
        write_json(
            artifacts.status,
            {"state": "running", "updated_at": datetime.now(timezone.utc).isoformat()},
        )
        remote_runner = (
            self._remote_process_runner(
                artifacts=artifacts,
                benchmark_input=artifacts.benchmark_input,
                json_results=json_results,
                repo_data=repo_data,
                temp_dir=temp_dir,
            )
            if self.execution_backend == "ssh-remote-envbench"
            else None
        )
        process_runner = remote_runner or _run_envbench_process
        container_cleanup = (
            remote_runner.cleanup_containers
            if remote_runner is not None
            else cleanup_case_containers
        )
        try:
            execution = EnvBenchCandidateExecutor(
                process_runner,
                ExactRevisionSourceCache,
                container_cleanup,
            ).execute(
                EnvBenchCandidateRequest(
                    case=case,
                    script=script,
                    benchmark_root=self.benchmark.root,
                    benchmark_input=artifacts.benchmark_input,
                    json_results=json_results,
                    repo_data=repo_data,
                    temp_dir=temp_dir,
                    image=self.image,
                    source_cache_root=(
                        self.config.runs_root / "_source_cache/envbench-python"
                        if self.preseed_source_cache
                        else None
                    ),
                    max_workers=self.config.max_workers,
                    process_timeout=self.config.evaluation_process_timeout,
                    create_container_timeout=self.config.create_container_timeout,
                    container_timeout=self.config.container_timeout,
                    git_fetch_timeout=self.config.git_fetch_timeout,
                    cleanup_root=artifacts.root,
                )
            )
        finally:
            if remote_runner is not None:
                try:
                    remote_runner.cleanup_staging()
                except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                    remote_runner.execution_metadata["staging_cleanup_error"] = (
                        f"{type(exc).__name__}: {exc}"
                    )
        started_at = execution.started_at
        command = list(execution.command)
        process_returncode = execution.process_returncode
        stdout = execution.stdout
        stderr = execution.stderr
        adapter_error = execution.adapter_error
        termination = execution.termination
        repository_acquisition = execution.repository_acquisition
        execution_backend = (
            remote_runner.execution_metadata
            if remote_runner is not None
            else {
                "kind": "local",
                "benchmark_root": str(self.benchmark.root),
            }
        )
        write_text_atomic(
            artifacts.evaluation_log,
            f"$ {' '.join(command)}\n\n[stdout]\n{stdout}\n[stderr]\n{stderr}",
        )

        result_path = execution.result_path
        raw = execution.raw

        pyright = raw.get("pyright")
        summary = pyright.get("summary") if isinstance(pyright, dict) else None
        if not isinstance(summary, dict):
            summary = {}
        exit_code = raw.get("exit_code")
        issues_count = raw.get("issues_count")
        identity_matches = execution.identity_matches
        completed = execution.completed
        raw_metrics = {
            "exit_code": exit_code,
            "issues_count": issues_count,
            "error_count": summary.get("errorCount"),
            "warning_count": summary.get("warningCount"),
            "repo_name": raw.get("repo_name", case.repository),
            "commit_sha": raw.get("commit_sha", case.revision),
        }
        official_pass = completed and self.protocol.is_official_pass(raw_metrics)
        artifact_path = (
            str(result_path.relative_to(artifacts.root)) if result_path.exists() else None
        )
        official_metrics = {
            "exit_code": exit_code,
            "issues_count": issues_count,
            "repo_name": raw.get("repo_name", case.repository),
            "commit_sha": raw.get("commit_sha", case.revision),
        }
        official_evidence = VerificationEvidence(
            verifier_id="envbench-official",
            channel="official",
            passed=official_pass if completed else None,
            summary=(
                "EnvBench official criteria satisfied"
                if official_pass
                else (
                    "EnvBench official evaluation incomplete"
                    if not completed
                    else "EnvBench official criteria not satisfied"
                )
            ),
            metrics=official_metrics,
            artifact_path=artifact_path,
        )
        diagnostic_evidence = build_envbench_diagnostic_evidence(
            raw,
            completed,
            artifact_path,
        )
        result = EvaluationResult(
            evaluation_completed=completed,
            official_pass=official_pass,
            benchmark=self.benchmark_id,
            case_id=case.case_id,
            execution_time=raw.get("execution_time"),
            evidence=(official_evidence, *diagnostic_evidence),
            raw_metrics=raw_metrics,
            raw_result_path=str(result_path.relative_to(artifacts.root)) if result_path.exists() else None,
            metadata={
                "adapter": "envbench",
                "adapter_version": "0.9.0",
                "harness_process_exit_code": process_returncode,
                "identity_matches": identity_matches,
                "adapter_error": adapter_error,
                "termination": termination,
                "repository_acquisition": repository_acquisition,
                "execution_backend": execution_backend,
                "started_at": started_at,
                "finished_at": execution.finished_at,
            },
        )
        write_json(artifacts.parsed_result, result.to_dict())
        update_manifest(
            artifacts,
            script={
                "path": str(artifacts.bootstrap_script.relative_to(artifacts.root)),
                "sha256": sha256_file(artifacts.bootstrap_script),
            },
            evaluator={
                **(
                    execution_backend.get("benchmark", {})
                    if remote_runner is not None
                    else git_provenance(self.benchmark.root)
                ),
                "benchmark": self.benchmark_id,
                "image": (
                    execution_backend.get("image", {})
                    if remote_runner is not None
                    else docker_image_provenance(self.image)
                ),
                "execution_backend": execution_backend,
                "source_hashes": (
                    execution_backend.get("benchmark", {}).get("source_hashes", {})
                    if remote_runner is not None
                    else {
                        "main.py": sha256_file(
                            self.benchmark.root / "evaluation/main.py"
                        ),
                        "python_build.sh": sha256_file(
                            self.benchmark.root / "evaluation/scripts/python_build.sh"
                        ),
                        "repo_downloader.py": sha256_file(
                            self.benchmark.root / "env_setup_utils/repo_downloader.py"
                        ),
                    }
                ),
                "command": command,
                "timeouts": {
                    "process": self.config.evaluation_process_timeout,
                    "create_container": self.config.create_container_timeout,
                    "container": self.config.container_timeout,
                    "git_fetch": self.config.git_fetch_timeout,
                },
                "repository_acquisition": repository_acquisition,
            },
            result=result.to_dict(),
        )
        write_json(
            artifacts.status,
            {
                "state": "completed" if completed else "failed",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "official_pass": result.official_pass,
            },
        )
        return result
