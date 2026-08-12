#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
from typing import Any, Protocol, TextIO

from envsolve.runtime.docker import (
    DockerEnvironmentHandle,
    DockerFreshEnvironmentProvider,
)
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.runtime.goal_verifier import ExecutableGoalContractVerifier
from envsolve.runtime.integrity import (
    marked_json_payload,
    python_import_alias_audit_command,
)
from envsolve.runtime.workspace import WorkspacePrecondition
from envsolve.solver import (
    DeploymentCandidate,
    CounterexampleEvidence,
    ExecutableVerification,
    FeedbackChannel,
    FreshEnvironmentProvider,
)
from envsolve_harness.codex.container_mcp import (
    CommandExecutor,
    ContainerMcpServer,
    PersistentContainerShell,
    _bounded_output,
)
from envsolve_harness.core.io import read_json, write_json, write_text_atomic
from envsolve_harness.integrity.repository import inspect_repository
from envsolve_harness.scripts.open_program import OpenCandidateProgramValidator


REPLAY_SCHEMA = "envsolve-pro-minimal-b-clean-replay-v1"
CERTIFICATION_SCHEMA = "envsolve-pro-minimal-b-certification-v1"
_LOCAL_DISTRIBUTION_BASELINE_MARKER = (
    "ENVSOLVE_PYTHON_INSTALLATION_BASELINE_V2="
)
_LOCAL_DISTRIBUTION_POST_MARKER = "ENVSOLVE_PYTHON_INSTALLATION_POST_V2="
_LOCAL_DISTRIBUTION_AUDIT = r"""\
import importlib.metadata
import json
from pathlib import Path
import site
import sys
import sysconfig
from urllib.parse import unquote, urlparse

project_root = Path(sys.argv[1]).resolve()
marker = sys.argv[2]

provided = set()
for base in (project_root, project_root / "src"):
    if not base.is_dir():
        continue
    for child in base.iterdir():
        if child.is_symlink():
            continue
        if child.is_file() and child.suffix in {".py", ".pyi"}:
            provided.add(child.stem)
        elif child.is_dir() and (
            (child / "__init__.py").is_file()
            or any(item.suffix in {".py", ".pyi"} for item in child.iterdir())
        ):
            provided.add(child.name)

distributions = list(importlib.metadata.distributions())
violations = []
owned_files = set()
for distribution in distributions:
    for item in distribution.files or ():
        try:
            owned_files.add(Path(distribution.locate_file(item)).resolve())
        except (OSError, RuntimeError):
            continue
    encoded = distribution.read_text("direct_url.json")
    if not encoded:
        continue
    try:
        direct_url = json.loads(encoded)
        parsed = urlparse(str(direct_url.get("url", "")))
    except (TypeError, ValueError, json.JSONDecodeError):
        continue
    if parsed.scheme != "file":
        continue

    top_level = {
        line.strip()
        for line in (distribution.read_text("top_level.txt") or "").splitlines()
        if line.strip().isidentifier()
    }
    if not top_level:
        for item in distribution.files or ():
            first = str(item).split("/", 1)[0]
            if first.endswith((".dist-info", ".egg-info")):
                continue
            if first.endswith((".py", ".pyi")):
                first = first.rsplit(".", 1)[0]
            if first.isidentifier():
                top_level.add(first)
    undeclared = sorted(top_level - provided)
    if not undeclared:
        continue
    origin = unquote(parsed.path)
    violations.append(
        {
            "audit_kind": "undeclared-local-distribution",
            "distribution": distribution.metadata.get("Name", "unknown"),
            "version": distribution.version,
            "origin": origin,
            "top_level_modules": sorted(top_level),
            "undeclared_modules": undeclared,
            "reason": (
                "local distribution exposes modules not provided by the repository"
            ),
        }
    )

site_roots = set()
try:
    site_roots.update(site.getsitepackages())
except Exception:
    pass
try:
    site_roots.add(site.getusersitepackages())
except Exception:
    pass
for key in ("purelib", "platlib"):
    value = sysconfig.get_paths().get(key)
    if value:
        site_roots.add(value)

unowned_import_artifacts = []
for encoded_root in sorted(site_roots):
    root = Path(encoded_root)
    if not root.is_dir():
        continue
    for path in root.rglob("*"):
        if not path.is_file() or not path.name.endswith(
            (".py", ".pyi", ".so", ".pyd", ".pth")
        ):
            continue
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError):
            continue
        if resolved in owned_files:
            continue
        unowned_import_artifacts.append(
            {
                "audit_kind": "unowned-import-artifact",
                "relative_path": str(path.relative_to(root)),
                "reason": (
                    "importable site-package artifact is not owned by an "
                    "installed distribution"
                ),
            }
        )

print(
    marker
    + json.dumps(
        {
            "valid": not violations and not unowned_import_artifacts,
            "violations": violations,
            "unowned_import_artifacts": unowned_import_artifacts,
            "provided_modules": sorted(provided),
        },
        sort_keys=True,
    )
)
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_script(script: str) -> str:
    return script.replace("\r\n", "\n").replace("\r", "\n").strip()


def script_sha256(script: str) -> str:
    return hashlib.sha256(canonical_script(script).encode("utf-8")).hexdigest()


def _local_distribution_audit_command(project_root: str, marker: str) -> str:
    return (
        f"command python -I -c {shlex.quote(_LOCAL_DISTRIBUTION_AUDIT)} "
        f"{shlex.quote(project_root)} {shlex.quote(marker)}"
    )


def _novel_local_distribution_violations(
    baseline: dict[str, Any],
    post: dict[str, Any],
) -> list[dict[str, Any]]:
    baseline_items: list[Any] = []
    post_items: list[Any] = []
    for key in ("violations", "unowned_import_artifacts"):
        baseline_value = baseline.get(key)
        post_value = post.get(key)
        if not isinstance(baseline_value, list) or not isinstance(post_value, list):
            raise ValueError("Python installation audit has malformed findings")
        baseline_items.extend(baseline_value)
        post_items.extend(post_value)
    known = {
        json.dumps(item, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        for item in baseline_items
        if isinstance(item, dict)
    }
    return [
        item
        for item in post_items
        if isinstance(item, dict)
        and json.dumps(
            item,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        not in known
    ]


class MinimalBExecutableGoalVerifier(ExecutableGoalContractVerifier):
    """Add Python installation provenance to the shared executable goal."""

    check_profile = "minimal-b-executable-goal-contract-v1"

    def _command(
        self,
        candidate: DeploymentCandidate,
        handle: DockerEnvironmentHandle,
        nonce: str,
    ) -> tuple[str, str, str]:
        command, completion_marker, report_begin = super()._command(
            candidate,
            handle,
            nonce,
        )
        baseline = _local_distribution_audit_command(
            handle.container_workdir,
            _LOCAL_DISTRIBUTION_BASELINE_MARKER,
        )
        command = f"{baseline}\n{command}"
        alias_audit = python_import_alias_audit_command(handle.container_workdir)
        if command.count(alias_audit) != 1:
            raise RuntimeError("cannot instrument Minimal B post-candidate audit")
        post = _local_distribution_audit_command(
            handle.container_workdir,
            _LOCAL_DISTRIBUTION_POST_MARKER,
        )
        command = command.replace(alias_audit, f"{post}\n{alias_audit}", 1)
        return command, completion_marker, report_begin

    def verify(
        self,
        candidate: DeploymentCandidate,
        environment: Any,
    ) -> ExecutableVerification:
        outcome = super().verify(candidate, environment)
        baseline = marked_json_payload(
            outcome.bootstrap.stdout,
            _LOCAL_DISTRIBUTION_BASELINE_MARKER,
        )
        post = marked_json_payload(
            outcome.bootstrap.stdout,
            _LOCAL_DISTRIBUTION_POST_MARKER,
        )
        if baseline is None or post is None:
            if outcome.bootstrap.exit_code != 0:
                return outcome
            return self._unknown(
                outcome.bootstrap,
                "Python installation provenance audit did not complete",
                {
                    "python_installation_provenance": {
                        "baseline_present": baseline is not None,
                        "post_present": post is not None,
                    }
                },
            )
        try:
            violations = _novel_local_distribution_violations(baseline, post)
        except ValueError as exc:
            return self._unknown(
                outcome.bootstrap,
                "Python installation provenance audit was malformed",
                {"python_installation_provenance_error": str(exc)},
            )
        if not violations:
            return outcome
        baseline_count = sum(
            len(baseline.get(key, []))
            for key in ("violations", "unowned_import_artifacts")
        )
        post_count = sum(
            len(post.get(key, []))
            for key in ("violations", "unowned_import_artifacts")
        )
        audit = {
            "valid": False,
            "violations": violations,
            "baseline_finding_count": baseline_count,
            "post_finding_count": post_count,
        }
        return ExecutableVerification(
            verifier="envsolve-pro-minimal-b-integrity-verifier",
            check_profile=self.check_profile,
            channel=FeedbackChannel.INTERNAL_EXECUTION,
            passed=False,
            bootstrap=outcome.bootstrap,
            summary="Candidate introduced an inadmissible Python installation artifact",
            counterexamples=(
                CounterexampleEvidence(
                    "python-installation-provenance",
                    audit,
                ),
            ),
            details={
                "goal_verification": outcome.details,
                "python_installation_provenance": audit,
            },
        )


class ReplayVerifier(Protocol):
    def verify(
        self,
        candidate: DeploymentCandidate,
        environment: Any,
    ) -> ExecutableVerification: ...


class CleanReplayService:
    """Validate and replay complete programs without retaining replay state."""

    def __init__(
        self,
        *,
        provider: FreshEnvironmentProvider,
        verifier: ReplayVerifier,
        repository: str,
        revision: str,
        image_digest: str,
        goal_contract_sha256: str,
        trace_path: Path,
        certification_path: Path,
        programs_root: Path,
        max_output_chars: int = 16_000,
    ) -> None:
        if max_output_chars <= 0:
            raise ValueError("Replay output bound must be positive")
        self.provider = provider
        self.verifier = verifier
        self.repository = repository
        self.revision = revision
        self.image_digest = image_digest
        self.goal_contract_sha256 = goal_contract_sha256
        self.trace_path = trace_path
        self.certification_path = certification_path
        self.programs_root = programs_root
        self.max_output_chars = max_output_chars
        self.validator = OpenCandidateProgramValidator()
        self.sequence = 0
        self.environment_ids: set[str] = set()
        self.certified_programs: list[dict[str, Any]] = []
        self._write_certification()

    def _write_certification(self) -> None:
        write_json(
            self.certification_path,
            {
                "schema": CERTIFICATION_SCHEMA,
                "repository": self.repository,
                "revision": self.revision,
                "image_digest": self.image_digest,
                "goal_contract_sha256": self.goal_contract_sha256,
                "replay_count": self.sequence,
                "certified_programs": self.certified_programs,
                "updated_at": _now(),
            },
        )

    def _trace(self, result: dict[str, Any]) -> None:
        record = {"recorded_at": _now(), **result}
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _bounded_text(self, value: str) -> tuple[str, bool]:
        return _bounded_output(value, self.max_output_chars)

    def _bounded_json(self, value: Any) -> dict[str, Any]:
        encoded = json.dumps(value, ensure_ascii=True, sort_keys=True)
        bounded, truncated = self._bounded_text(encoded)
        return {"json": bounded, "truncated": truncated}

    def _verification(self, outcome: ExecutableVerification) -> dict[str, Any]:
        stdout, stdout_truncated = self._bounded_text(outcome.bootstrap.stdout)
        stderr, stderr_truncated = self._bounded_text(outcome.bootstrap.stderr)
        return {
            "verifier": outcome.verifier,
            "check_profile": outcome.check_profile,
            "feedback_channel": outcome.channel.value,
            "passed": outcome.passed,
            "summary": outcome.summary,
            "bootstrap": {
                "exit_code": outcome.bootstrap.exit_code,
                "stdout": stdout,
                "stdout_truncated": stdout_truncated,
                "stderr": stderr,
                "stderr_truncated": stderr_truncated,
                "duration_seconds": outcome.bootstrap.duration_seconds,
            },
            "observations": self._bounded_json(
                [asdict(item) for item in outcome.observations]
            ),
            "counterexamples": self._bounded_json(
                [asdict(item) for item in outcome.counterexamples]
            ),
            "details": self._bounded_json(outcome.details),
        }

    def _finish(self, result: dict[str, Any]) -> dict[str, Any]:
        self._trace(result)
        self._write_certification()
        return result

    def submit(self, program: str) -> dict[str, Any]:
        self.sequence += 1
        replay_id = f"minimal-b-replay-{self.sequence:04d}"
        canonical = canonical_script(program)
        digest = script_sha256(canonical)
        program_path = self.programs_root / f"{replay_id}.sh"
        write_text_atomic(program_path, canonical + ("\n" if canonical else ""))
        base: dict[str, Any] = {
            "schema": REPLAY_SCHEMA,
            "replay_id": replay_id,
            "replay_index": self.sequence,
            "program_sha256": digest,
            "program_artifact": f"{self.programs_root.name}/{program_path.name}",
            "certified": False,
        }
        if not canonical:
            return self._finish(
                {
                    **base,
                    "status": "fail",
                    "phase": "candidate-validation",
                    "candidate_validation": {
                        "accepted": False,
                        "policy_id": self.validator.policy_id,
                        "reason": "candidate program is empty",
                        "details": {},
                    },
                }
            )

        candidate = DeploymentCandidate(
            candidate_id=replay_id,
            script=canonical,
            rationale="Minimal B in-session clean replay submission",
            metadata={
                "environment_fresh": True,
                "execution_role": "in-session-clean-replay",
            },
        )
        validation = self.validator.validate(candidate)
        validation_result = {
            "accepted": validation.accepted,
            "policy_id": validation.policy_id,
            "reason": validation.reason,
            "details": validation.details,
        }
        base["candidate_validation"] = validation_result
        if not validation.accepted:
            return self._finish(
                {
                    **base,
                    "status": "fail",
                    "phase": "candidate-validation",
                }
            )

        canonical = canonical_script(validation.normalized_script or canonical)
        digest = script_sha256(canonical)
        write_text_atomic(program_path, canonical + "\n")
        candidate = DeploymentCandidate(
            candidate_id=replay_id,
            script=canonical,
            rationale=candidate.rationale,
            metadata=candidate.metadata,
        )
        base["program_sha256"] = digest
        environment = None
        outcome: ExecutableVerification | None = None
        infrastructure_error: str | None = None
        release_error: str | None = None
        try:
            environment = self.provider.provision(candidate)
            receipt = environment.receipt
            if (
                receipt.environment_id in self.environment_ids
                or receipt.repository != self.repository
                or receipt.revision != self.revision
                or receipt.image_digest != self.image_digest
            ):
                raise RuntimeError("fresh replay provider returned an invalid receipt")
            self.environment_ids.add(receipt.environment_id)
            base["environment_receipt"] = receipt.to_dict()
            outcome = self.verifier.verify(candidate, environment)
            if not isinstance(outcome, ExecutableVerification):
                raise RuntimeError("clean replay verifier returned a malformed result")
            if outcome.channel is not FeedbackChannel.INTERNAL_EXECUTION:
                raise RuntimeError("clean replay used a forbidden feedback channel")
        except Exception as exc:
            infrastructure_error = f"{type(exc).__name__}: {exc}"
        finally:
            if environment is not None:
                try:
                    self.provider.release(environment)
                except Exception as exc:
                    release_error = f"{type(exc).__name__}: {exc}"

        if infrastructure_error is not None or release_error is not None:
            return self._finish(
                {
                    **base,
                    "status": "infrastructure_error",
                    "phase": "clean-replay",
                    "infrastructure_error": infrastructure_error,
                    "release_error": release_error,
                    **(
                        {"verification": self._verification(outcome)}
                        if outcome is not None
                        else {}
                    ),
                }
            )
        if outcome is None:
            raise AssertionError("replay outcome must exist without infrastructure failure")

        verification = self._verification(outcome)
        if outcome.passed is None:
            status = "unknown"
        elif outcome.passed:
            if outcome.bootstrap.exit_code != 0 or outcome.counterexamples:
                return self._finish(
                    {
                        **base,
                        "status": "infrastructure_error",
                        "phase": "verification-contract",
                        "infrastructure_error": (
                            "passing verification contradicts bootstrap or counterexamples"
                        ),
                        "verification": verification,
                    }
                )
            status = "pass"
        else:
            status = "fail"

        result = {
            **base,
            "status": status,
            "phase": "clean-replay",
            "verification": verification,
            "certified": status == "pass",
        }
        if status == "pass":
            certificate = {
                "replay_id": replay_id,
                "program_sha256": digest,
                "environment_receipt": base["environment_receipt"],
                "certified_at": _now(),
            }
            self.certified_programs.append(certificate)
            result["certificate"] = certificate
        return self._finish(result)


class MinimalBMcpServer:
    protocol_version = "2025-06-18"
    replay_tool_name = "submit_and_replay"

    def __init__(
        self,
        executor: CommandExecutor,
        command_trace_path: Path,
        replay_service: CleanReplayService,
    ) -> None:
        self.terminal = ContainerMcpServer(executor, command_trace_path)
        self.replay_service = replay_service

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        request_id = request.get("id")
        method = request.get("method")
        if method == "initialize":
            requested = request.get("params", {}).get("protocolVersion")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": (
                        requested if isinstance(requested, str) else self.protocol_version
                    ),
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {
                        "name": "envsolve-pro-minimal-b",
                        "version": "1.0.2",
                    },
                    "instructions": (
                        "Use envbench_shell for all construction-environment work. "
                        "Use submit_and_replay to test a complete bootstrap program in "
                        "a distinct clean environment; its result returns to this session."
                    ),
                },
            }
        if method in {"notifications/initialized", "notifications/cancelled"}:
            return None
        if method == "ping":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        if method == "tools/list":
            terminal_tools = self.terminal.handle(
                {"jsonrpc": "2.0", "id": request_id, "method": "tools/list"}
            )
            if terminal_tools is None:
                raise AssertionError("terminal tool listing is missing")
            tools = list(terminal_tools["result"]["tools"])
            tools.append(
                {
                    "name": self.replay_tool_name,
                    "description": (
                        "Validate and execute one complete self-contained bootstrap "
                        "program in a new clean checkout and container, run the public "
                        "goal and repository-effect audit, release that environment, "
                        "and return the evidence to this same Agent session."
                    ),
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "program": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 100000,
                                "description": "Complete bootstrap Bash program.",
                            }
                        },
                        "required": ["program"],
                        "additionalProperties": False,
                    },
                    "annotations": {
                        "readOnlyHint": False,
                        "destructiveHint": False,
                        "idempotentHint": False,
                        "openWorldHint": True,
                    },
                }
            )
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": tools},
            }
        if method != "tools/call":
            if request_id is None:
                return None
            return self._error(request_id, -32601, f"unsupported method: {method}")

        params = request.get("params")
        if not isinstance(params, dict):
            return self._error(request_id, -32602, "tool params must be an object")
        if params.get("name") == self.terminal.tool_name:
            return self.terminal.handle(request)
        if params.get("name") != self.replay_tool_name:
            return self._error(request_id, -32602, "unknown tool")
        arguments = params.get("arguments")
        if not isinstance(arguments, dict) or not isinstance(
            arguments.get("program"), str
        ):
            return self._error(request_id, -32602, "program must be a string")
        if set(arguments) != {"program"}:
            return self._error(request_id, -32602, "unexpected replay arguments")
        result = self.replay_service.submit(arguments["program"])
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=True, sort_keys=True),
                    }
                ],
                "structuredContent": result,
                "isError": result["status"] == "infrastructure_error",
            },
        }

    def serve(self, input_stream: TextIO, output_stream: TextIO) -> None:
        try:
            for line in input_stream:
                if not line.strip():
                    continue
                try:
                    request = json.loads(line)
                    if not isinstance(request, dict):
                        raise ValueError("request must be an object")
                    response = self.handle(request)
                except (json.JSONDecodeError, ValueError) as exc:
                    response = self._error(None, -32700, str(exc))
                if response is not None:
                    output_stream.write(json.dumps(response, ensure_ascii=True) + "\n")
                    output_stream.flush()
        finally:
            self.terminal.executor.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="EnvSolve-Pro Minimal B terminal and clean replay MCP server."
    )
    parser.add_argument("--container-id", required=True)
    parser.add_argument("--workdir", default="/data/project")
    parser.add_argument("--command-trace", type=Path, required=True)
    parser.add_argument("--replay-trace", type=Path, required=True)
    parser.add_argument("--certification", type=Path, required=True)
    parser.add_argument("--programs-root", type=Path, required=True)
    parser.add_argument("--source-repository", type=Path, required=True)
    parser.add_argument("--worktrees", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--goal-contract", type=Path, required=True)
    parser.add_argument("--workspace-preconditions", type=Path, required=True)
    parser.add_argument("--command-timeout", type=int, required=True)
    parser.add_argument("--container-create-timeout", type=int, required=True)
    parser.add_argument("--max-output-chars", type=int, default=16000)
    parser.add_argument("--docker", default="docker")
    return parser.parse_args()


def _workspace_preconditions(path: Path) -> tuple[WorkspacePrecondition, ...]:
    value = read_json(path)
    if not isinstance(value, list):
        raise ValueError("workspace preconditions must be an array")
    return tuple(WorkspacePrecondition(**item) for item in value)


def main() -> int:
    args = parse_args()
    contract = ExecutableGoalContract.from_dict(read_json(args.goal_contract))
    preconditions = _workspace_preconditions(args.workspace_preconditions)
    provider = DockerFreshEnvironmentProvider(
        source_repository=args.source_repository,
        worktrees_root=args.worktrees,
        repository=args.repository,
        revision=args.revision,
        image=args.image,
        workspace_preconditions=preconditions,
        create_timeout=args.container_create_timeout,
    )
    verifier = MinimalBExecutableGoalVerifier(
        contract,
        observation_timeout=args.command_timeout,
        effect_auditor=lambda worktree: inspect_repository(
            worktree,
            args.revision,
            required_preconditions=preconditions,
        ),
    )
    replay_service = CleanReplayService(
        provider=provider,
        verifier=verifier,
        repository=args.repository,
        revision=args.revision,
        image_digest=args.image,
        goal_contract_sha256=contract.sha256,
        trace_path=args.replay_trace,
        certification_path=args.certification,
        programs_root=args.programs_root,
        max_output_chars=args.max_output_chars,
    )
    executor = PersistentContainerShell(
        args.container_id,
        args.workdir,
        args.command_timeout,
        args.max_output_chars,
        args.docker,
    )
    MinimalBMcpServer(executor, args.command_trace, replay_service).serve(
        sys.stdin,
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
