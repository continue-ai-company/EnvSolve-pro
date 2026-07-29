from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any

from envsolve_harness.core.io import read_json, read_jsonl, write_json, write_text_atomic
from envsolve_harness.core.models import Case, RunSpec, SolverResult
from envsolve_harness.execution.batch import cleanup_case_containers, terminate_process_group
from envsolve_harness.integrity.repository import inspect_repository
from envsolve_harness.scripts.open_program import OpenCandidateProgramValidator
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve_harness.storage.manifest import update_manifest
from envsolve_harness.utils.provenance import sha256_file
from envsolve.runtime.workspace import WorkspacePrecondition
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.solver import CandidateValidation, DeploymentCandidate


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "bootstrap_script": {"type": "string", "minLength": 1},
        "summary": {"type": "string"},
    },
    "required": ["bootstrap_script", "summary"],
    "additionalProperties": False,
}


def _toml(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def parse_codex_usage(records: list[dict[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for record in records:
        if record.get("type") != "turn.completed":
            continue
        usage = record.get("usage")
        if not isinstance(usage, dict):
            continue
        for name, value in usage.items():
            if isinstance(value, int) and not isinstance(value, bool):
                totals[str(name)] = totals.get(str(name), 0) + value
    return totals


def audit_script_grounding(
    script: str,
    command_records: list[dict[str, Any]],
) -> dict[str, Any]:
    successful = [
        str(record.get("command", "")).strip()
        for record in command_records
        if record.get("exit_code") == 0 and not record.get("timed_out")
    ]
    script_lines = [
        line.strip()
        for line in script.splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
        and line.strip() not in {"set -e", "set -eu", "set -euo pipefail"}
    ]
    grounded = [
        line
        for line in script_lines
        if any(line == command or line in command.splitlines() for command in successful)
    ]
    return {
        "policy": "successful-container-command-line-overlap-v1",
        "script_line_count": len(script_lines),
        "grounded_line_count": len(grounded),
        "ungrounded_lines": [line for line in script_lines if line not in grounded],
        "is_gate": False,
    }


def validate_codex_bootstrap(script: str) -> CandidateValidation:
    return OpenCandidateProgramValidator().validate(
        DeploymentCandidate(
            candidate_id="codex-bootstrap",
            script=script,
            rationale="Codex CLI final bootstrap submission",
        )
    )


def codex_validation_metadata(
    validation: CandidateValidation,
) -> dict[str, Any]:
    return {
        "accepted": validation.accepted,
        "policy_id": validation.policy_id,
        "reason": validation.reason,
        "details": validation.details,
    }


class CodexCliRunner:
    def __init__(
        self,
        *,
        codex_executable: Path,
        harness_root: Path,
        image: str,
        timeout: int,
        command_timeout: int,
        container_create_timeout: int,
        git_fetch_timeout: int,
        reasoning_effort: str | None = None,
        workspace_preconditions: tuple[WorkspacePrecondition, ...] = (),
        goal_contract: ExecutableGoalContract | None = None,
    ) -> None:
        self.codex_executable = codex_executable
        self.harness_root = harness_root
        self.image = image
        self.timeout = timeout
        self.command_timeout = command_timeout
        self.container_create_timeout = container_create_timeout
        self.git_fetch_timeout = git_fetch_timeout
        self.reasoning_effort = reasoning_effort or "high"
        self.workspace_preconditions = workspace_preconditions
        self.goal_contract = goal_contract

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _redact(value: str) -> str:
        return re.sub(
            r"(?<![A-Za-z0-9])sk-(?:proj-|or-v1-)?[A-Za-z0-9_-]{16,}",
            "[REDACTED]",
            value,
        )

    @staticmethod
    def _checked(
        command: list[str],
        *,
        timeout: int,
        cwd: Path | None = None,
    ) -> str:
        process = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if process.returncode != 0:
            detail = process.stderr.strip() or process.stdout.strip()
            raise RuntimeError(f"{' '.join(command[:3])} failed: {detail}")
        return process.stdout.strip()

    def _finish(
        self,
        artifacts: RunArtifacts,
        result: SolverResult,
        log: str,
    ) -> SolverResult:
        write_json(artifacts.solver_result, result.to_dict())
        write_text_atomic(artifacts.solver_log, self._redact(log))
        update_manifest(artifacts, solver=result.to_dict())
        write_json(
            artifacts.status,
            {
                "state": "generated" if result.generation_completed else "failed",
                "updated_at": self._now(),
            },
        )
        return result

    def _acquire_repository(self, case: Case, destination: Path) -> list[list[str]]:
        destination.mkdir(parents=True, exist_ok=False)
        commands = [
            ["git", "init", "-q"],
            ["git", "remote", "add", "origin", f"https://github.com/{case.repository}.git"],
        ]
        for command in commands:
            self._checked(command, cwd=destination, timeout=self.git_fetch_timeout)
        fetch = ["git", "fetch", "--depth", "1", "origin", case.revision]
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                self._checked(fetch, cwd=destination, timeout=self.git_fetch_timeout)
                last_error = None
                break
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2**attempt)
        if last_error is not None:
            raise RuntimeError(f"repository fetch failed after 3 attempts: {last_error}")
        checkout = ["git", "checkout", "--detach", "FETCH_HEAD"]
        self._checked(checkout, cwd=destination, timeout=self.git_fetch_timeout)
        revision = self._checked(
            ["git", "rev-parse", "HEAD"],
            cwd=destination,
            timeout=self.git_fetch_timeout,
        )
        if revision != case.revision:
            raise RuntimeError(f"checked out {revision}, expected {case.revision}")
        return [*commands, fetch, checkout]

    def _image_digest(self) -> str:
        inspect = ["docker", "image", "inspect", "--format", "{{.Id}}", self.image]
        try:
            return self._checked(inspect, timeout=self.container_create_timeout)
        except RuntimeError:
            self._checked(
                ["docker", "pull", self.image],
                timeout=max(self.container_create_timeout, 900),
            )
            return self._checked(inspect, timeout=self.container_create_timeout)

    def _materialize_workspace_preconditions(self, workspace: Path) -> None:
        for precondition in self.workspace_preconditions:
            precondition.materialize(workspace)

    def _create_container(self, workspace: Path, image_digest: str) -> str:
        container_id = self._checked(
            [
                "docker",
                "create",
                "--init",
                "--entrypoint",
                "/bin/bash",
                "--mount",
                f"type=bind,src={workspace},dst=/data/project",
                "--workdir",
                "/data/project",
                image_digest,
                "-lc",
                "while true; do sleep 1000; done",
            ],
            timeout=self.container_create_timeout,
        )
        try:
            self._checked(
                ["docker", "start", container_id],
                timeout=self.container_create_timeout,
            )
        except Exception:
            subprocess.run(
                ["docker", "rm", "-f", container_id],
                capture_output=True,
                text=True,
                check=False,
            )
            raise
        return container_id

    def _prompt(
        self,
        case: Case,
        goal_contract: ExecutableGoalContract | None = None,
    ) -> str:
        prompt = f"""\
Act as a strong general-purpose coding agent whose sole task is to set up the
Python development environment for `{case.repository}` at exact revision
`{case.revision}`.

The repository is mounted at `/data/project` in a persistent EnvBench Docker
container. Use `envsolve_container.envbench_shell` for every inspection,
installation, and verification step. The Bash shell, current directory,
exported variables, installed packages, and filesystem persist across calls.
The checkout already contains any benchmark-adapter-owned workspace state that
will be present before the submitted bootstrap script runs. Preserve that state.
You have no access to the official EnvBench evaluator or any evaluator result.

Explore the repository and its documentation, infer the intended Python and
dependency-manager setup, install all necessary project and development
dependencies, and use ordinary execution feedback to diagnose failures. Do not
modify tracked source files, dependency declarations, lockfiles, tests, or type
checker configuration. Install the checked-out local project rather than a
same-named package from a registry. Do not use sudo or interactive commands.

When the environment is ready, return the requested JSON object. Its
`bootstrap_script` must be a self-contained Bash script that can be sourced from
the root of a fresh checkout in the same base image. Include only the successful
environment setup commands needed to reproduce the final state; omit inspection,
diagnostic, test, and failed commands. The script must not edit repository source
or configuration. `summary` should briefly state what was installed.

The submitted script will be checked against this shared candidate contract:
<candidate_contract>
{OpenCandidateProgramValidator.prompt_contract}
</candidate_contract>
"""
        if goal_contract is None:
            return prompt
        return (
            prompt
            + "\n"
            + f"""\
The following public executable goal is the authoritative success criterion.
You may run it during diagnosis. It is not a post-hoc evaluator result, and no
official evaluator output is available.

Goal ID: {goal_contract.contract_id}
Goal description: {goal_contract.description}
Goal report schema: {goal_contract.report_schema}
Goal contract SHA-256: {goal_contract.sha256}

Trusted goal program:
<goal_program>
{goal_contract.program}
</goal_program>

Optimize the bootstrap script for this goal. Tests, documentation builds, and
other development checks are optional evidence rather than the success criterion.
"""
        )

    def _codex_command(
        self,
        *,
        run_spec: RunSpec,
        control_dir: Path,
        schema_path: Path,
        output_path: Path,
        trace_path: Path,
        container_id: str,
    ) -> list[str]:
        server_args = [
            "-m",
            "envsolve_harness.codex.container_mcp",
            "--container-id",
            container_id,
            "--workdir",
            "/data/project",
            "--trace",
            str(trace_path),
            "--command-timeout",
            str(self.command_timeout),
            "--max-output-chars",
            "16000",
            "--docker",
            shutil.which("docker") or "docker",
        ]
        overrides = {
            "approval_policy": "never",
            "project_doc_max_bytes": 0,
            "web_search": "disabled",
            "model_reasoning_effort": self.reasoning_effort,
            "features.shell_tool": False,
            "features.apps": False,
            "features.goals": False,
            "features.hooks": False,
            "features.memories": False,
            "features.multi_agent": False,
            "features.remote_plugin": False,
            "mcp_servers.envsolve_container.command": sys.executable,
            "mcp_servers.envsolve_container.args": server_args,
            "mcp_servers.envsolve_container.cwd": str(self.harness_root),
            "mcp_servers.envsolve_container.required": True,
            "mcp_servers.envsolve_container.enabled_tools": ["envbench_shell"],
            "mcp_servers.envsolve_container.tool_timeout_sec": self.command_timeout + 30,
            "mcp_servers.envsolve_container.default_tools_approval_mode": "approve",
            "mcp_servers.envsolve_container.tools.envbench_shell.approval_mode": "approve",
        }
        command = [
            str(self.codex_executable),
            "exec",
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--model",
            str(run_spec.model),
            "--cd",
            str(control_dir),
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
        ]
        for name, value in overrides.items():
            command.extend(["--config", f"{name}={_toml(value)}"])
        command.append("-")
        return command

    def run(self, case: Case, artifacts: RunArtifacts, run_spec: RunSpec) -> SolverResult:
        started_at = self._now()
        write_json(artifacts.status, {"state": "generating", "updated_at": started_at})
        metadata: dict[str, Any] = {
            "runner": "codex-cli",
            "runner_version": "0.1.0",
            "baseline_interface": "native-codex-agent+container-terminal-mcp-v1",
            "official_evaluator_access": "post-episode-only",
            "audit_requirements": {"repository_integrity": True},
            "resource_policy": {
                "generation_wall_clock_safety_cap_seconds": self.timeout,
                "container_command_safety_cap_seconds": self.command_timeout,
                "token_usage_is_hard_limit": False,
                "cost_is_hard_limit": False,
            },
            "model_reasoning_effort": self.reasoning_effort,
            "image_reference": self.image,
            "workspace_preconditions": [
                item.to_dict() for item in self.workspace_preconditions
            ],
            "started_at": started_at,
        }
        goal_contract = (
            self.goal_contract
            if run_spec.method == "codex-cli-goal-aware"
            else None
        )
        if goal_contract is not None:
            metadata["goal_contract"] = {
                "contract_id": goal_contract.contract_id,
                "report_schema": goal_contract.report_schema,
                "sha256": goal_contract.sha256,
            }
        if not run_spec.model:
            return self._finish(
                artifacts,
                SolverResult(False, run_spec.method, error="Codex CLI requires RunSpec.model", metadata=metadata),
                "Codex CLI requires a model identifier.\n",
            )
        if not self.codex_executable.is_file():
            return self._finish(
                artifacts,
                SolverResult(
                    False,
                    run_spec.method,
                    error=f"Codex CLI executable is missing: {self.codex_executable}",
                    metadata=metadata,
                ),
                "Codex CLI executable is missing.\n",
            )

        control_dir = artifacts.generation_dir / "codex-control"
        workspace = artifacts.generation_dir / "workspace"
        control_dir.mkdir(parents=True, exist_ok=True)
        schema_path = control_dir / "output-schema.json"
        output_path = control_dir / "final-output.json"
        events_path = artifacts.trajectory_jsonl
        trace_path = artifacts.generation_dir / "container-commands.jsonl"
        prompt_path = control_dir / "prompt.txt"
        write_json(schema_path, OUTPUT_SCHEMA)
        write_text_atomic(prompt_path, self._prompt(case, goal_contract))

        container_id: str | None = None
        log_parts: list[str] = []
        try:
            acquisition_commands = self._acquire_repository(case, workspace)
            self._materialize_workspace_preconditions(workspace)
            metadata["repository_acquisition"] = {
                "source": "github-exact-revision",
                "commands": acquisition_commands,
                "attempts": 3,
            }
            image_digest = self._image_digest()
            metadata["image_digest"] = image_digest
            container_id = self._create_container(workspace, image_digest)

            version = subprocess.run(
                [str(self.codex_executable), "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            metadata["codex_cli"] = {
                "version": version.stdout.strip() or version.stderr.strip(),
                "executable": str(self.codex_executable),
            }
            command = self._codex_command(
                run_spec=run_spec,
                control_dir=control_dir,
                schema_path=schema_path,
                output_path=output_path,
                trace_path=trace_path,
                container_id=container_id,
            )
            metadata["command"] = command
            process_env = os.environ.copy()
            for name in (
                "OPENAI_API_KEY",
                "OPENAI_BASE_URL",
                "OPENROUTER_API_KEY",
                "ANTHROPIC_API_KEY",
            ):
                process_env.pop(name, None)
            process = subprocess.Popen(
                command,
                cwd=self.harness_root,
                env=process_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            timed_out = False
            try:
                stdout, stderr = process.communicate(
                    input=prompt_path.read_text(encoding="utf-8"),
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired:
                timed_out = True
                terminate_process_group(process)
                stdout, stderr = process.communicate()
            write_text_atomic(events_path, stdout)
            log_parts.append(
                f"$ {' '.join(command)}\n\n[stdout]\n{stdout}\n[stderr]\n{stderr}"
            )
            metadata["process_exit_code"] = process.returncode
            metadata["timed_out"] = timed_out
            try:
                records = read_jsonl(events_path)
            except ValueError as exc:
                records = []
                metadata["event_parse_error"] = str(exc)
            metadata["token_usage"] = parse_codex_usage(records)
            command_records = read_jsonl(trace_path) if trace_path.is_file() else []
            successful_command_count = sum(
                1
                for record in command_records
                if record.get("exit_code") == 0
                and not record.get("timed_out")
                and not record.get("infrastructure_error")
            )
            metadata["container_command_trace"] = {
                "path": str(trace_path.relative_to(artifacts.root)),
                "sha256": sha256_file(trace_path) if trace_path.is_file() else None,
                "count": len(command_records),
                "successful_count": successful_command_count,
            }
            integrity = inspect_repository(
                workspace,
                case.revision,
                required_preconditions=self.workspace_preconditions,
            )
            metadata["repository_integrity"] = integrity.to_dict()
            metadata["checked_out_revision"] = integrity.checked_out_revision

            if timed_out:
                metadata["termination"] = {
                    "kind": "safety_cap_exhausted",
                    "scope": "generation_wall_clock",
                    "limit_seconds": self.timeout,
                }
                raise RuntimeError("Codex CLI exceeded the generation safety cap")
            if process.returncode != 0:
                raise RuntimeError(f"Codex CLI exited with {process.returncode}")
            if successful_command_count == 0:
                raise RuntimeError(
                    "Codex CLI completed without a successful container command"
                )
            if not output_path.is_file():
                raise RuntimeError("Codex CLI did not produce its structured final output")
            submission = read_json(output_path)
            if not isinstance(submission, dict) or not isinstance(
                submission.get("bootstrap_script"), str
            ):
                raise RuntimeError("Codex CLI final output does not match the output schema")
            script = submission["bootstrap_script"].strip()
            if not script:
                raise RuntimeError("Codex CLI returned an empty bootstrap script")
            if len(script) > 100_000:
                raise RuntimeError("Codex CLI bootstrap script exceeds 100000 characters")
            validation = validate_codex_bootstrap(script)
            metadata["candidate_validation"] = codex_validation_metadata(validation)
            if not validation.accepted:
                raise RuntimeError(
                    "Codex CLI bootstrap script violates the shared candidate "
                    f"policy: {validation.reason}"
                )
            script = (validation.normalized_script or script).strip()
            metadata["submission"] = {
                "summary": str(submission.get("summary", "")),
                "script_grounding": audit_script_grounding(script, command_records),
                "output_path": str(output_path.relative_to(artifacts.root)),
                "prompt_sha256": sha256_file(prompt_path),
                "schema_sha256": sha256_file(schema_path),
            }
            if not integrity.valid:
                raise RuntimeError(
                    f"Codex CLI repository integrity failed: {integrity.to_dict()['violations']}"
                )
            write_text_atomic(artifacts.generated_script, script + "\n")
            result = SolverResult(
                True,
                run_spec.method,
                script_path=str(artifacts.generated_script.relative_to(artifacts.root)),
                trajectory_path=str(events_path.relative_to(artifacts.root)),
                metadata={**metadata, "finished_at": self._now()},
            )
            return self._finish(artifacts, result, "\n".join(log_parts))
        except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
            if workspace.is_dir() and "repository_integrity" not in metadata:
                try:
                    metadata["repository_integrity"] = inspect_repository(
                        workspace,
                        case.revision,
                        required_preconditions=self.workspace_preconditions,
                    ).to_dict()
                except Exception:
                    pass
            result = SolverResult(
                False,
                run_spec.method,
                trajectory_path=(
                    str(events_path.relative_to(artifacts.root))
                    if events_path.is_file()
                    else None
                ),
                error=f"{type(exc).__name__}: {exc}",
                metadata={**metadata, "finished_at": self._now()},
            )
            log_parts.append(f"{type(exc).__name__}: {exc}\n")
            return self._finish(artifacts, result, "\n".join(log_parts))
        finally:
            if container_id:
                subprocess.run(
                    [
                        "docker",
                        "exec",
                        "--user",
                        "0:0",
                        container_id,
                        "chown",
                        "-R",
                        f"{os.getuid()}:{os.getgid()}",
                        "/data/project",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                subprocess.run(
                    ["docker", "rm", "-f", container_id],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            cleanup_case_containers(artifacts.root)
