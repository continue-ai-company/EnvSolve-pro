from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from difflib import unified_diff
from pathlib import Path
from typing import Any, Literal

from envsolve_harness.codex.minimal_b_mcp import canonical_script
from envsolve_harness.core.io import read_json, write_json


PROGRESS_STATE_SCHEMA = "envsolve-pro-project-progress-v1"
EvidenceStatus = Literal["pass", "fail", "unknown", "infrastructure_error"]


def _nonempty(value: str, name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be empty")
    return normalized


@dataclass(frozen=True)
class DeploymentCondition:
    condition_id: str
    operating_system: str
    architecture: str
    python_version: str
    image: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "condition_id",
            "operating_system",
            "architecture",
            "python_version",
        ):
            object.__setattr__(self, name, _nonempty(getattr(self, name), name))
        if self.image is not None:
            object.__setattr__(self, "image", _nonempty(self.image, "image"))

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DeploymentCondition":
        return cls(
            condition_id=str(value["condition_id"]),
            operating_system=str(value["operating_system"]),
            architecture=str(value["architecture"]),
            python_version=str(value["python_version"]),
            image=(str(value["image"]) if value.get("image") is not None else None),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def delta(
        self, target: "DeploymentCondition"
    ) -> dict[str, dict[str, str | None]]:
        result: dict[str, dict[str, str | None]] = {}
        for name in ("operating_system", "architecture", "python_version", "image"):
            before = getattr(self, name)
            after = getattr(target, name)
            if before != after:
                result[name] = {"from": before, "to": after}
        return result


@dataclass(frozen=True)
class ExecutionEvidence:
    status: EvidenceStatus
    source: str
    bootstrap_exit_code: int | None
    public_goal_passed: bool | None
    observed_python: str | None = None
    duration_seconds: float | None = None
    failure_summary: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"pass", "fail", "unknown", "infrastructure_error"}:
            raise ValueError(f"Unsupported evidence status: {self.status}")
        object.__setattr__(self, "source", _nonempty(self.source, "source"))
        if self.bootstrap_exit_code is not None and (
            isinstance(self.bootstrap_exit_code, bool)
            or not isinstance(self.bootstrap_exit_code, int)
        ):
            raise ValueError("bootstrap_exit_code must be an integer or null")
        if self.public_goal_passed is not None and not isinstance(
            self.public_goal_passed, bool
        ):
            raise ValueError("public_goal_passed must be boolean or null")
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("duration_seconds cannot be negative")
        for name in ("observed_python", "failure_summary"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _nonempty(value, name))
        if self.status == "pass" and (
            self.bootstrap_exit_code != 0 or self.public_goal_passed is not True
        ):
            raise ValueError(
                "passing evidence requires bootstrap 0 and a passing public goal"
            )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ExecutionEvidence":
        return cls(
            status=value["status"],
            source=str(value["source"]),
            bootstrap_exit_code=value.get("bootstrap_exit_code"),
            public_goal_passed=value.get("public_goal_passed"),
            observed_python=(
                str(value["observed_python"])
                if value.get("observed_python") is not None
                else None
            ),
            duration_seconds=value.get("duration_seconds"),
            failure_summary=(
                str(value["failure_summary"])
                if value.get("failure_summary") is not None
                else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeploymentRecord:
    condition: DeploymentCondition
    program: str
    evidence: ExecutionEvidence

    def __post_init__(self) -> None:
        normalized = canonical_script(self.program)
        if not normalized:
            raise ValueError("verified deployment program cannot be empty")
        object.__setattr__(self, "program", normalized)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DeploymentRecord":
        return cls(
            condition=DeploymentCondition.from_dict(value["condition"]),
            program=str(value["program"]),
            evidence=ExecutionEvidence.from_dict(value["evidence"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition": self.condition.to_dict(),
            "program": self.program,
            "evidence": self.evidence.to_dict(),
        }


@dataclass(frozen=True)
class RepairRecord:
    target_condition: DeploymentCondition
    trigger: ExecutionEvidence
    program_delta: str
    result: ExecutionEvidence

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RepairRecord":
        return cls(
            target_condition=DeploymentCondition.from_dict(value["target_condition"]),
            trigger=ExecutionEvidence.from_dict(value["trigger"]),
            program_delta=str(value["program_delta"]),
            result=ExecutionEvidence.from_dict(value["result"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_condition": self.target_condition.to_dict(),
            "trigger": self.trigger.to_dict(),
            "program_delta": self.program_delta,
            "result": self.result.to_dict(),
        }


@dataclass(frozen=True)
class ProjectProgressState:
    version: int
    case_id: str
    repository: str
    revision: str
    current_program: str
    current_condition: DeploymentCondition
    deployments: tuple[DeploymentRecord, ...]
    repairs: tuple[RepairRecord, ...] = ()
    unresolved_risks: tuple[str, ...] = ()
    schema_version: str = field(default=PROGRESS_STATE_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.version, bool)
            or not isinstance(self.version, int)
            or self.version < 1
        ):
            raise ValueError("progress state version must be a positive integer")
        for name in ("case_id", "repository", "revision"):
            object.__setattr__(self, name, _nonempty(getattr(self, name), name))
        normalized = canonical_script(self.current_program)
        if not normalized:
            raise ValueError("current program cannot be empty")
        object.__setattr__(self, "current_program", normalized)
        if not self.deployments:
            raise ValueError("progress state requires execution evidence")
        if not any(
            item.evidence.status == "pass"
            and item.program == normalized
            and item.condition == self.current_condition
            for item in self.deployments
        ):
            raise ValueError(
                "current program and condition require matching successful evidence"
            )
        for risk in self.unresolved_risks:
            _nonempty(risk, "unresolved risk")

    @classmethod
    def start(
        cls,
        *,
        case_id: str,
        repository: str,
        revision: str,
        program: str,
        condition: DeploymentCondition,
        evidence: ExecutionEvidence,
        unresolved_risks: tuple[str, ...] = (),
    ) -> "ProjectProgressState":
        if evidence.status != "pass":
            raise ValueError("initial progress state requires a successful deployment")
        deployment = DeploymentRecord(condition, program, evidence)
        return cls(
            version=1,
            case_id=case_id,
            repository=repository,
            revision=revision,
            current_program=program,
            current_condition=condition,
            deployments=(deployment,),
            unresolved_risks=unresolved_risks,
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ProjectProgressState":
        if value.get("schema_version") != PROGRESS_STATE_SCHEMA:
            raise ValueError("unsupported project progress schema")
        return cls(
            version=value["version"],
            case_id=str(value["case_id"]),
            repository=str(value["repository"]),
            revision=str(value["revision"]),
            current_program=str(value["current_program"]),
            current_condition=DeploymentCondition.from_dict(value["current_condition"]),
            deployments=tuple(
                DeploymentRecord.from_dict(item) for item in value["deployments"]
            ),
            repairs=tuple(
                RepairRecord.from_dict(item) for item in value.get("repairs", [])
            ),
            unresolved_risks=tuple(
                str(item) for item in value.get("unresolved_risks", [])
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "version": self.version,
            "case_id": self.case_id,
            "repository": self.repository,
            "revision": self.revision,
            "current_program": self.current_program,
            "current_condition": self.current_condition.to_dict(),
            "deployments": [item.to_dict() for item in self.deployments],
            "repairs": [item.to_dict() for item in self.repairs],
            "unresolved_risks": list(self.unresolved_risks),
        }

    def record(
        self,
        *,
        condition: DeploymentCondition,
        program: str,
        evidence: ExecutionEvidence,
        trigger: ExecutionEvidence | None = None,
        unresolved_risks: tuple[str, ...] | None = None,
    ) -> "ProjectProgressState":
        normalized = canonical_script(program)
        deployment = DeploymentRecord(condition, normalized, evidence)
        repairs = self.repairs
        if trigger is not None:
            if trigger.status == "pass":
                raise ValueError(
                    "a repair trigger must describe a non-passing execution"
                )
            delta = "\n".join(
                unified_diff(
                    self.current_program.splitlines(),
                    normalized.splitlines(),
                    fromfile="previous-program",
                    tofile="updated-program",
                    lineterm="",
                )
            )
            repairs += (RepairRecord(condition, trigger, delta, evidence),)
        next_program = normalized if evidence.status == "pass" else self.current_program
        next_condition = (
            condition if evidence.status == "pass" else self.current_condition
        )
        risks = self.unresolved_risks if unresolved_risks is None else unresolved_risks
        return replace(
            self,
            version=self.version + 1,
            current_program=next_program,
            current_condition=next_condition,
            deployments=self.deployments + (deployment,),
            repairs=repairs,
            unresolved_risks=risks,
        )

    def compact_context(self, target: DeploymentCondition) -> str:
        latest = self.deployments[-1]
        lines = [
            f"Project: {self.repository}@{self.revision}",
            f"Progress state version: {self.version}",
            "Target condition: " + _condition_text(target),
            "Condition change: " + _delta_text(self.current_condition.delta(target)),
            "Latest execution evidence: " + _evidence_text(latest.evidence),
            "Latest verified program:",
            "<verified_program>",
            self.current_program,
            "</verified_program>",
        ]
        if self.repairs:
            repair = self.repairs[-1]
            lines.extend(
                [
                    "Latest observed failure-to-repair transition:",
                    f"Trigger: {_evidence_text(repair.trigger)}",
                    "Program delta:",
                    repair.program_delta or "(program unchanged)",
                    f"Result: {_evidence_text(repair.result)}",
                ]
            )
        if self.unresolved_risks:
            lines.append("Unresolved observed risks:")
            lines.extend(f"- {item}" for item in self.unresolved_risks)
        else:
            lines.append("Unresolved observed risks: none recorded")
        return "\n".join(lines)


def _condition_text(condition: DeploymentCondition) -> str:
    image = f", image={condition.image}" if condition.image else ""
    return (
        f"id={condition.condition_id}, os={condition.operating_system}, "
        f"arch={condition.architecture}, python={condition.python_version}{image}"
    )


def _delta_text(delta: dict[str, dict[str, str | None]]) -> str:
    if not delta:
        return "none"
    return "; ".join(
        f"{name}: {values['from']} -> {values['to']}"
        for name, values in sorted(delta.items())
    )


def _evidence_text(evidence: ExecutionEvidence) -> str:
    fields = [
        f"status={evidence.status}",
        f"source={evidence.source}",
        f"bootstrap_exit={evidence.bootstrap_exit_code}",
        f"public_goal_passed={evidence.public_goal_passed}",
    ]
    if evidence.observed_python:
        fields.append(f"observed_python={evidence.observed_python}")
    if evidence.failure_summary:
        fields.append(f"failure={evidence.failure_summary}")
    return ", ".join(fields)


def load_progress_state(path: Path) -> ProjectProgressState:
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError("project progress state must be a JSON object")
    return ProjectProgressState.from_dict(value)


def save_progress_snapshot(root: Path, state: ProjectProgressState) -> Path:
    path = root / f"state-v{state.version:04d}.json"
    if path.exists():
        raise FileExistsError(f"progress state snapshot already exists: {path}")
    write_json(path, state.to_dict())
    return path
