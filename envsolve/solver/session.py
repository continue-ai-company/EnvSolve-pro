from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable, Protocol

from envsolve.solver.artifacts import ImmutableArtifactStore
from envsolve.state import EventStore, EventType, StateEvent


SECRET_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])sk-(?:proj-|or-v1-)?[A-Za-z0-9_-]{16,}"
)
TERMINAL_OUTPUT_LIMIT = 16_000


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float | None = None

    def __post_init__(self) -> None:
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("CommandResult.exit_code must be an integer")
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("CommandResult.duration_seconds cannot be negative")


class ActionExecutor(Protocol):
    def execute(self, command: str) -> CommandResult: ...


@dataclass(frozen=True)
class ActionSpec:
    action_type: str
    command: str
    rationale: str
    preconditions: tuple[str, ...] = ()
    action_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


class SolverStateSession:
    def __init__(
        self,
        event_log: Path,
        snapshot_path: Path,
        case: dict[str, Any],
        redactor: Callable[[str], str] | None = None,
        artifact_store: ImmutableArtifactStore | None = None,
        run_id: str | None = None,
        episode_id: str = "episode-0001",
    ) -> None:
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("Solver state case requires a non-empty case_id")
        self.case = dict(case)
        self.store = EventStore(event_log, case_id)
        self.snapshot_path = snapshot_path
        self.redactor = redactor or (lambda value: SECRET_PATTERN.sub("[REDACTED]", value))
        self.artifact_store = artifact_store or ImmutableArtifactStore(
            event_log.parent / "raw-artifacts"
        )
        self.run_id = run_id or f"run-{case_id}"
        self.episode_id = episode_id
        if not self.run_id.strip() or not self.episode_id.strip():
            raise ValueError("Solver state run_id and episode_id cannot be empty")
        events = self.store.read()
        if events:
            reconstructed = self.store.reconstruct()
            if reconstructed.case != self.case:
                raise ValueError("Existing state trajectory belongs to a different case")
            trace = events[0].payload.get("trace")
            if isinstance(trace, dict) and (
                trace.get("run_id") != self.run_id
                or trace.get("episode_id") != self.episode_id
            ):
                raise ValueError("Existing state trajectory belongs to a different episode")
        else:
            self.store.append(
                EventType.RUN_STARTED,
                {
                    "case": self.case,
                    "trace": {
                        "run_id": self.run_id,
                        "episode_id": self.episode_id,
                        "step_id": "step-000000",
                    },
                },
            )
        self.refresh_snapshot()

    @property
    def case_id(self) -> str:
        return str(self.case["case_id"])

    def reconstruct(self):
        return self.store.reconstruct()

    def refresh_snapshot(self) -> dict[str, Any]:
        snapshot = self.reconstruct().to_dict()
        _write_json_atomic(self.snapshot_path, snapshot)
        return snapshot

    def _append(self, event_type: EventType, payload: dict[str, Any]) -> StateEvent:
        next_sequence = self.reconstruct().last_sequence + 1
        event = self.store.append(
            event_type,
            {
                **payload,
                "trace": {
                    "run_id": self.run_id,
                    "episode_id": self.episode_id,
                    "step_id": f"step-{next_sequence:06d}",
                },
            },
        )
        self.refresh_snapshot()
        return event

    def _next_id(self, prefix: str, existing: set[str]) -> str:
        index = 1
        while f"{prefix}-{index:04d}" in existing:
            index += 1
        return f"{prefix}-{index:04d}"

    def _safe_text(self, value: str) -> str:
        redacted = self.redactor(value)
        if len(redacted) <= TERMINAL_OUTPUT_LIMIT:
            return redacted
        omitted = len(redacted) - TERMINAL_OUTPUT_LIMIT
        return f"{redacted[:TERMINAL_OUTPUT_LIMIT]}\n...[truncated {omitted} characters]"

    def _artifact(self, value: str, *, suffix: str = ".txt") -> dict[str, Any]:
        return self.artifact_store.put_text(
            self.redactor(value), suffix=suffix
        ).to_dict()

    def _safe_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._safe_text(value)
        if isinstance(value, dict):
            return {str(key): self._safe_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._safe_value(item) for item in value]
        return value

    def profile_repository(self, profile: dict[str, Any]) -> StateEvent:
        return self._append(
            EventType.REPOSITORY_PROFILED,
            {"profile": self._safe_value(profile)},
        )

    def record_evidence(
        self,
        kind: str,
        source: str,
        value: Any,
        confidence: float = 1.0,
        evidence_id: str | None = None,
        candidate_id: str | None = None,
        parent_candidate_id: str | None = None,
        environment_id: str | None = None,
    ) -> str:
        state = self.reconstruct()
        identifier = evidence_id or self._next_id("evidence", set(state.evidence))
        payload = {
            "evidence_id": identifier,
            "kind": self._safe_text(kind),
            "source": self._safe_text(source),
            "value": self._safe_value(value),
            "confidence": confidence,
        }
        if candidate_id is not None:
            payload["candidate_id"] = candidate_id
        if parent_candidate_id is not None:
            payload["parent_candidate_id"] = parent_candidate_id
        if environment_id is not None:
            payload["environment_id"] = environment_id
        self._append(EventType.EVIDENCE_RECORDED, payload)
        return identifier

    def upsert_constraint(
        self,
        constraint_id: str,
        kind: str,
        expression: str,
        status: str,
        evidence_ids: tuple[str, ...] | list[str],
    ) -> StateEvent:
        return self._append(
            EventType.CONSTRAINT_UPSERTED,
            {
                "constraint_id": constraint_id,
                "kind": self._safe_text(kind),
                "expression": self._safe_text(expression),
                "status": status,
                "evidence_ids": list(evidence_ids),
            },
        )

    def upsert_goal(self, goal_id: str, description: str, status: str) -> StateEvent:
        return self._append(
            EventType.GOAL_UPSERTED,
            {
                "goal_id": goal_id,
                "description": self._safe_text(description),
                "status": status,
            },
        )

    def upsert_hypothesis(
        self,
        hypothesis_id: str,
        statement: str,
        confidence: float,
        evidence_ids: tuple[str, ...] | list[str],
        status: str = "active",
    ) -> StateEvent:
        return self._append(
            EventType.HYPOTHESIS_UPSERTED,
            {
                "hypothesis_id": hypothesis_id,
                "statement": self._safe_text(statement),
                "confidence": confidence,
                "evidence_ids": list(evidence_ids),
                "status": status,
            },
        )

    def update_environment(self, name: str, value: Any, source: str) -> StateEvent:
        return self._append(
            EventType.ENVIRONMENT_UPDATED,
            {
                "name": name,
                "value": self._safe_value(value),
                "source": self._safe_text(source),
            },
        )

    def _action_id(self, requested: str | None) -> str:
        state = self.reconstruct()
        return requested or self._next_id("action", set(state.actions))

    def propose_action(self, spec: ActionSpec) -> str:
        action_id = self._action_id(spec.action_id)
        payload = {
            "action_id": action_id,
            "action_type": spec.action_type,
            "command": self._safe_text(spec.command),
            "rationale": self._safe_text(spec.rationale),
            "preconditions": list(spec.preconditions),
        }
        if spec.metadata:
            payload["metadata"] = self._safe_value(spec.metadata)
        payload["command_artifact"] = self._artifact(spec.command, suffix=".sh")
        self._append(EventType.ACTION_PROPOSED, payload)
        return action_id

    def start_action(self, action_id: str) -> StateEvent:
        return self._append(EventType.ACTION_STARTED, {"action_id": action_id})

    def finish_action(self, action_id: str, result: CommandResult) -> StateEvent:
        observation = {
            "stdout": self._safe_text(result.stdout),
            "stderr": self._safe_text(result.stderr),
            "duration_seconds": result.duration_seconds,
            "stdout_artifact": self._artifact(result.stdout),
            "stderr_artifact": self._artifact(result.stderr),
        }
        return self._append(
            EventType.ACTION_FINISHED,
            {
                "action_id": action_id,
                "exit_code": result.exit_code,
                "observation": observation,
            },
        )

    def record_failure(
        self,
        category: str,
        message: str,
        action_id: str | None = None,
        details: dict[str, Any] | None = None,
        failure_id: str | None = None,
    ) -> str:
        state = self.reconstruct()
        identifier = failure_id or self._next_id("failure", set(state.failures))
        payload: dict[str, Any] = {
            "failure_id": identifier,
            "category": category,
            "message": self._safe_text(message),
        }
        if action_id is not None:
            payload["action_id"] = action_id
        if details:
            payload["details"] = self._safe_value(details)
        self._append(EventType.FAILURE_RECORDED, payload)
        return identifier

    def _record_action_evidence(
        self,
        action_id: str,
        spec: ActionSpec,
        result: CommandResult,
        evidence_id: str | None = None,
        evidence_source: str = "solver-action",
    ) -> str:
        return self.record_evidence(
            kind="action-result",
            source=evidence_source,
            value={
                "action_id": action_id,
                "command": spec.command,
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration_seconds": result.duration_seconds,
            },
            confidence=1.0,
            evidence_id=evidence_id,
        )

    def record_action_result(
        self,
        spec: ActionSpec,
        result: CommandResult,
        evidence_id: str | None = None,
        evidence_source: str = "recorded-action",
    ) -> str:
        action_id = self.propose_action(spec)
        self.start_action(action_id)
        self.complete_recorded_action(
            action_id,
            spec,
            result,
            evidence_id=evidence_id,
            evidence_source=evidence_source,
        )
        return action_id

    def complete_recorded_action(
        self,
        action_id: str,
        spec: ActionSpec,
        result: CommandResult,
        evidence_id: str | None = None,
        evidence_source: str = "recorded-action",
    ) -> None:
        """Complete an externally executed action that is already running."""
        self.finish_action(action_id, result)
        self._record_action_evidence(
            action_id,
            spec,
            result,
            evidence_id=evidence_id,
            evidence_source=evidence_source,
        )
        if result.exit_code != 0:
            self.record_failure(
                category="command-exit",
                message=f"Action exited with code {result.exit_code}",
                action_id=action_id,
                details={"exit_code": result.exit_code},
            )

    def execute_action(self, spec: ActionSpec, executor: ActionExecutor) -> CommandResult:
        action_id = self.propose_action(spec)
        self.start_action(action_id)
        try:
            result = executor.execute(spec.command)
        except Exception as exc:
            result = CommandResult(
                exit_code=255,
                stderr=f"{type(exc).__name__}: {exc}",
            )
            self.finish_action(action_id, result)
            self._record_action_evidence(action_id, spec, result)
            self.record_failure(
                category="executor-exception",
                message=result.stderr,
                action_id=action_id,
            )
            return result
        self.finish_action(action_id, result)
        self._record_action_evidence(action_id, spec, result)
        if result.exit_code != 0:
            self.record_failure(
                category="command-exit",
                message=f"Action exited with code {result.exit_code}",
                action_id=action_id,
                details={"exit_code": result.exit_code},
            )
        return result

    def record_verification(
        self,
        level: str,
        verifier: str,
        passed: bool | None,
        details: dict[str, Any],
        verification_id: str | None = None,
    ) -> str:
        state = self.reconstruct()
        existing = {
            str(item.get("verification_id")) for item in state.verifications
        }
        identifier = verification_id or self._next_id("verification", existing)
        self._append(
            EventType.VERIFICATION_RECORDED,
            {
                "verification_id": identifier,
                "level": level,
                "verifier": self._safe_text(verifier),
                "passed": passed,
                "details": self._safe_value(details),
            },
        )
        return identifier
