from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from envsolve.context import CONTEXT_EVIDENCE_KINDS, build_repair_context
from envsolve.solver import SolverStateSession
from envsolve.state import EnvironmentState


IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class ImageIdentity:
    reference: str
    image_id: str
    repo_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise ValueError("Image reference cannot be empty")
        if not IMAGE_ID.fullmatch(self.image_id):
            raise ValueError(f"Invalid image ID: {self.image_id!r}")
        object.__setattr__(
            self,
            "repo_digests",
            tuple(sorted(set(self.repo_digests))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference": self.reference,
            "id": self.image_id,
            "repo_digests": list(self.repo_digests),
        }


@dataclass(frozen=True)
class ContextTransferLineage:
    source_case_id: str
    source_snapshot_hash: str
    source_event_log_sha256: str
    source_summary_sha256: str
    target_manifest_sha256: str
    target_audit_sha256: str
    target_raw_result_path: str
    target_raw_result_sha256: str

    def __post_init__(self) -> None:
        if not self.source_case_id or not self.target_raw_result_path:
            raise ValueError("Context transfer lineage identities cannot be empty")
        for name, value in asdict(self).items():
            if name.endswith("sha256") or name == "source_snapshot_hash":
                if not re.fullmatch(r"[0-9a-f]{64}", value):
                    raise ValueError(f"Invalid lineage hash {name}: {value!r}")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ContextTransferReport:
    transferred_evidence_ids: tuple[str, ...]
    appended_evidence: int
    profile_appended: bool
    image: ImageIdentity
    lineage: ContextTransferLineage

    def to_dict(self) -> dict[str, Any]:
        return {
            "transferred_evidence_ids": list(self.transferred_evidence_ids),
            "appended_evidence": self.appended_evidence,
            "profile_appended": self.profile_appended,
            "image": self.image.to_dict(),
            "lineage": self.lineage.to_dict(),
        }


def _without_metadata(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "state_metadata"}


def _target_evidence_id(source_evidence_id: str) -> str:
    suffix = re.sub(r"[^A-Za-z0-9_.-]+", "-", source_evidence_id).strip("-")
    if not suffix:
        raise ValueError(f"Invalid source evidence ID: {source_evidence_id!r}")
    return f"evidence-transferred-{suffix}"


def transfer_context_evidence(
    source_state: EnvironmentState,
    target_session: SolverStateSession,
    source_image: ImageIdentity,
    target_image: ImageIdentity,
    lineage: ContextTransferLineage,
) -> ContextTransferReport:
    if source_image != target_image:
        raise ValueError("Context source and target image identities do not match")
    if source_state.case_id != lineage.source_case_id:
        raise ValueError("Context source state does not match transfer lineage")
    if source_state.to_dict()["snapshot_hash"] != lineage.source_snapshot_hash:
        raise ValueError("Context source snapshot hash does not match transfer lineage")

    context_report = build_repair_context(source_state)
    selected = tuple(context_report.context.evidence_ids)
    if not selected:
        raise ValueError("Context source has no selected evidence to transfer")
    payloads: list[tuple[str, dict[str, Any], str]] = []
    for source_id in selected:
        record = source_state.evidence.get(source_id)
        if record is None or record.get("kind") not in CONTEXT_EVIDENCE_KINDS:
            raise ValueError(f"Selected context evidence is invalid: {source_id}")
        target_id = _target_evidence_id(source_id)
        payloads.append((source_id, record, target_id))

    profile = {
        "kind": "p4c-context-transfer",
        "source_case_id": source_state.case_id,
        "source_snapshot_hash": lineage.source_snapshot_hash,
        "image": source_image.to_dict(),
        "lineage": lineage.to_dict(),
        "selected_source_evidence_ids": list(selected),
    }
    target_state = target_session.reconstruct()
    current_profile = _without_metadata(target_state.repository_profile)
    if current_profile and current_profile != profile:
        raise ValueError("Target state already has a different repository profile")
    for source_id, record, target_id in payloads:
        existing = target_state.evidence.get(target_id)
        expected_source = (
            f"context-transfer:{source_state.case_id}:"
            f"{lineage.source_snapshot_hash}:{source_image.image_id}:{source_id}"
        )
        if existing is not None and (
            existing.get("kind") != record.get("kind")
            or existing.get("source") != expected_source
            or existing.get("value") != record.get("value")
            or existing.get("confidence") != record.get("confidence")
        ):
            raise ValueError(f"Target evidence collision: {target_id}")

    profile_appended = not bool(current_profile)
    if profile_appended:
        target_session.profile_repository(profile)
    appended = 0
    transferred: list[str] = []
    for source_id, record, target_id in payloads:
        transferred.append(target_id)
        if target_id in target_session.reconstruct().evidence:
            continue
        target_session.record_evidence(
            kind=str(record["kind"]),
            source=(
                f"context-transfer:{source_state.case_id}:"
                f"{lineage.source_snapshot_hash}:{source_image.image_id}:{source_id}"
            ),
            value=record["value"],
            confidence=float(record["confidence"]),
            evidence_id=target_id,
        )
        appended += 1
    return ContextTransferReport(
        transferred_evidence_ids=tuple(transferred),
        appended_evidence=appended,
        profile_appended=profile_appended,
        image=source_image,
        lineage=lineage,
    )
