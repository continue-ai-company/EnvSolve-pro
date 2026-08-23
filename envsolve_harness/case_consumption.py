from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class ConsumptionEvidence:
    case_id: str
    kind: str
    source: str
    run_id: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {key: value for key, value in asdict(self).items() if value is not None}


def read_case_ids(path: Path) -> list[str]:
    case_ids: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        payload = json.loads(line)
        case_id = payload.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"Missing case_id at {path}:{line_number}")
        case_ids.append(case_id)
    if len(case_ids) != len(set(case_ids)):
        raise ValueError(f"Duplicate case identity in {path}")
    return case_ids


def registry_evidence(path: Path) -> list[ConsumptionEvidence]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    trajectories = payload.get("trajectories")
    if not isinstance(trajectories, list):
        raise ValueError(f"Historical registry has no trajectories list: {path}")

    evidence: list[ConsumptionEvidence] = []
    for row in trajectories:
        if not isinstance(row, dict):
            continue
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            continue
        observed_attempts = row.get("observed_attempt_count")
        has_execution_evidence = (
            isinstance(row.get("trajectory_sha256"), str)
            or (isinstance(observed_attempts, int) and observed_attempts > 0)
        )
        if not has_execution_evidence:
            continue
        run_id = row.get("run_id")
        evidence.append(
            ConsumptionEvidence(
                case_id=case_id,
                kind="historical-trajectory-registry",
                source=str(path),
                run_id=run_id if isinstance(run_id, str) else None,
            )
        )
    return evidence


def _case_id_from_artifact(artifact_root: Path) -> str:
    case_path = artifact_root / "inputs" / "case.json"
    payload = json.loads(case_path.read_text(encoding="utf-8"))
    case_id = payload.get("case_id")
    if isinstance(case_id, str) and case_id:
        return case_id
    repository = payload.get("repository")
    revision = payload.get("revision")
    if isinstance(repository, str) and isinstance(revision, str):
        return f"envbench-python-{repository.replace('/', '__')}@{revision}"
    raise ValueError(f"Cannot recover case identity from {case_path}")


def run_evidence(runs_root: Path) -> list[ConsumptionEvidence]:
    evidence: list[ConsumptionEvidence] = []
    for trajectory_path in sorted(runs_root.glob("**/generation/trajectory.jsonl")):
        provider_observed = False
        with trajectory_path.open(encoding="utf-8") as trajectory:
            for line in trajectory:
                if not line.strip():
                    continue
                event = json.loads(line)
                if event.get("event") == "provider_response":
                    provider_observed = True
                    break
        if not provider_observed:
            continue
        artifact_root = trajectory_path.parent.parent
        case_id = _case_id_from_artifact(artifact_root)
        run_id = artifact_root.parent.name or None
        evidence.append(
            ConsumptionEvidence(
                case_id=case_id,
                kind="model-provider-response",
                source=str(trajectory_path),
                run_id=run_id,
            )
        )
    return evidence


def audit_case_consumption(
    case_ids: Iterable[str],
    *,
    registry_paths: Iterable[Path] = (),
    runs_roots: Iterable[Path] = (),
) -> dict[str, Any]:
    ordered_ids = list(case_ids)
    if len(ordered_ids) != len(set(ordered_ids)):
        raise ValueError("Candidate case identities must be unique")

    all_evidence: list[ConsumptionEvidence] = []
    for path in registry_paths:
        all_evidence.extend(registry_evidence(path))
    for root in runs_roots:
        all_evidence.extend(run_evidence(root))

    by_case: dict[str, dict[tuple[str, str, str | None], ConsumptionEvidence]] = {
        case_id: {} for case_id in ordered_ids
    }
    for item in all_evidence:
        if item.case_id not in by_case:
            continue
        key = (item.kind, item.source, item.run_id)
        by_case[item.case_id][key] = item

    cases = []
    for case_id in ordered_ids:
        evidence = sorted(
            by_case[case_id].values(),
            key=lambda item: (item.kind, item.source, item.run_id or ""),
        )
        cases.append(
            {
                "case_id": case_id,
                "consumed": bool(evidence),
                "evidence": [item.to_dict() for item in evidence],
            }
        )
    consumed_count = sum(bool(row["consumed"]) for row in cases)
    return {
        "schema": "envsolve-case-consumption-audit-v1",
        "candidate_count": len(cases),
        "consumed_count": consumed_count,
        "unconsumed_count": len(cases) - consumed_count,
        "cases": cases,
    }
