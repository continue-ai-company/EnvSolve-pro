from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from envsolve.solver import DeploymentCandidate
from envsolve_harness.adapters.envbench_executor import (
    withheld_envbench_feedback_payload,
)
from envsolve_harness.codex.minimal_b_mcp import (
    CERTIFICATION_SCHEMA,
    REPLAY_SCHEMA,
    MinimalBMcpServer,
    canonical_script,
    script_sha256,
)
from envsolve_harness.core.io import write_json, write_text_atomic
from envsolve_harness.scripts.open_program import OpenCandidateProgramValidator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def matched_replay_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Project real and withheld replay results onto one stable model-visible shape."""
    verification = result.get("verification")
    if not isinstance(verification, dict):
        verification = {}
    bootstrap = verification.get("bootstrap")
    if not isinstance(bootstrap, dict):
        bootstrap = {}
    return {
        "schema": "envsolve-pro-matched-clean-replay-feedback-v1",
        "replay_id": result.get("replay_id"),
        "replay_index": result.get("replay_index"),
        "program_sha256": result.get("program_sha256"),
        "program_artifact": result.get("program_artifact"),
        "status": result.get("status"),
        "phase": result.get("phase"),
        "candidate_validation": result.get("candidate_validation"),
        "environment_receipt": result.get("environment_receipt"),
        "verification": {
            "verifier": verification.get("verifier"),
            "check_profile": verification.get("check_profile"),
            "feedback_channel": verification.get("feedback_channel"),
            "passed": verification.get("passed"),
            "summary": verification.get("summary"),
            "bootstrap": {
                "exit_code": bootstrap.get("exit_code"),
                "stdout": bootstrap.get("stdout"),
                "stdout_truncated": bootstrap.get("stdout_truncated"),
                "stderr": bootstrap.get("stderr"),
                "stderr_truncated": bootstrap.get("stderr_truncated"),
                "duration_seconds": bootstrap.get("duration_seconds"),
            },
            "observations": verification.get("observations"),
            "counterexamples": verification.get("counterexamples"),
            "details": verification.get("details"),
        },
        "certified": result.get("certified") is True,
        "certificate": result.get("certificate"),
        "infrastructure_error": result.get("infrastructure_error"),
        "release_error": result.get("release_error"),
        "withheld": result.get("status") == "withheld",
    }


def matched_envbench_replay_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Project EnvBench-path real and withheld results onto one response shape."""
    raw_feedback = result.get("feedback")
    if isinstance(raw_feedback, dict):
        raw_bootstrap = raw_feedback.get("bootstrap")
        raw_goal = raw_feedback.get("goal_report")
        bootstrap = raw_bootstrap if isinstance(raw_bootstrap, dict) else {}
        goal_report = raw_goal if isinstance(raw_goal, dict) else {}
        feedback = {
            "schema_version": raw_feedback.get("schema_version"),
            "status": raw_feedback.get("status"),
            "withheld": raw_feedback.get("withheld"),
            "bootstrap": {
                "terminal_class": bootstrap.get("terminal_class"),
                "exit_code": bootstrap.get("exit_code"),
                "git_ownership_error": bootstrap.get("git_ownership_error"),
            },
            "goal_report": {
                "present": goal_report.get("present"),
                "issues_count": goal_report.get("issues_count"),
                "error_count": goal_report.get("error_count"),
            },
            "missing_imports": raw_feedback.get("missing_imports"),
            "active_project_python": raw_feedback.get("active_project_python"),
            "infrastructure": raw_feedback.get("infrastructure"),
        }
    else:
        feedback = withheld_envbench_feedback_payload()
        if result.get("status") != "withheld":
            feedback = {**feedback, "status": "unavailable", "withheld": False}
    return {
        "schema": "envsolve-pro-matched-envbench-replay-feedback-v2",
        "replay_id": result.get("replay_id"),
        "replay_index": result.get("replay_index"),
        "program_sha256": result.get("program_sha256"),
        "program_artifact": result.get("program_artifact"),
        "status": result.get("status"),
        "phase": result.get("phase"),
        "candidate_validation": result.get("candidate_validation"),
        "environment_receipt": result.get("environment_receipt"),
        "feedback": feedback,
        "certified": result.get("certified") is True,
        "certificate": result.get("certificate"),
        "infrastructure_error": result.get("infrastructure_error"),
        "withheld": result.get("status") == "withheld",
    }


class WithheldReplayService:
    """Record a candidate submission while withholding target-state evidence."""

    def __init__(
        self,
        *,
        repository: str,
        revision: str,
        image_digest: str,
        goal_contract_sha256: str,
        trace_path: Path,
        certification_path: Path,
        programs_root: Path,
        replay_id_prefix: str = "minimal-b-replay",
        phase: str = "clean-replay",
    ) -> None:
        self.repository = repository
        self.revision = revision
        self.image_digest = image_digest
        self.goal_contract_sha256 = goal_contract_sha256
        self.trace_path = trace_path
        self.certification_path = certification_path
        self.programs_root = programs_root
        self.replay_id_prefix = replay_id_prefix
        self.phase = phase
        self.validator = OpenCandidateProgramValidator()
        self.sequence = 0
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
                "certified_programs": [],
                "updated_at": _now(),
            },
        )

    def _finish(self, result: dict[str, Any]) -> dict[str, Any]:
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {"recorded_at": _now(), **result},
                    ensure_ascii=True,
                    sort_keys=True,
                )
                + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        self._write_certification()
        return result

    def submit(self, program: str) -> dict[str, Any]:
        self.sequence += 1
        replay_id = f"{self.replay_id_prefix}-{self.sequence:04d}"
        canonical = canonical_script(program)
        digest = script_sha256(canonical)
        program_path = self.programs_root / f"{replay_id}.sh"
        write_text_atomic(program_path, canonical + ("\n" if canonical else ""))
        candidate = DeploymentCandidate(
            candidate_id=replay_id,
            script=canonical,
            rationale="Matched replay control submission",
        )
        validation = self.validator.validate(candidate)
        result: dict[str, Any] = {
            "schema": REPLAY_SCHEMA,
            "replay_id": replay_id,
            "replay_index": self.sequence,
            "program_sha256": digest,
            "program_artifact": f"{self.programs_root.name}/{program_path.name}",
            "candidate_validation": {
                "accepted": validation.accepted,
                "policy_id": validation.policy_id,
                "reason": validation.reason,
                "details": validation.details,
            },
            "certified": False,
        }
        if not validation.accepted:
            return self._finish(
                {**result, "status": "fail", "phase": "candidate-validation"}
            )
        return self._finish(
            {
                **result,
                "status": "withheld",
                "phase": self.phase,
            }
        )


class MatchedMinimalBMcpServer(MinimalBMcpServer):
    """Expose the same replay response shape in the real and withheld arms."""

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        response = super().handle(request)
        params = request.get("params")
        if (
            response is None
            or request.get("method") != "tools/call"
            or not isinstance(params, dict)
            or params.get("name") != self.replay_tool_name
        ):
            return response
        rpc_result = response.get("result")
        if not isinstance(rpc_result, dict):
            return response
        raw = rpc_result.get("structuredContent")
        if not isinstance(raw, dict):
            return response
        projected = matched_replay_payload(raw)
        rpc_result["structuredContent"] = projected
        rpc_result["content"] = [
            {
                "type": "text",
                "text": json.dumps(projected, ensure_ascii=True, sort_keys=True),
            }
        ]
        rpc_result["isError"] = projected["status"] == "infrastructure_error"
        return response


class MatchedEnvBenchMinimalBMcpServer(MinimalBMcpServer):
    """Expose matched EnvBench-path replay feedback in both experiment arms."""

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        response = super().handle(request)
        params = request.get("params")
        if (
            response is None
            or request.get("method") != "tools/call"
            or not isinstance(params, dict)
            or params.get("name") != self.replay_tool_name
        ):
            return response
        rpc_result = response.get("result")
        if not isinstance(rpc_result, dict):
            return response
        raw = rpc_result.get("structuredContent")
        if not isinstance(raw, dict):
            return response
        projected = matched_envbench_replay_payload(raw)
        rpc_result["structuredContent"] = projected
        rpc_result["content"] = [
            {
                "type": "text",
                "text": json.dumps(projected, ensure_ascii=True, sort_keys=True),
            }
        ]
        rpc_result["isError"] = projected["status"] == "infrastructure_error"
        return response
