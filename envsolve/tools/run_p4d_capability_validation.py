#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any
import uuid


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve.context import build_repair_context
from envsolve.discovery import AptFileDiscoveryPolicy
from envsolve.provenance import (
    ContextTransferLineage,
    ImageIdentity,
    transfer_context_evidence,
)
from envsolve.repairs import (
    RepairConstraintEngine,
    RepairKind,
    RepairRegistry,
    TypedRepairPolicy,
    preflight_repair,
)
from envsolve.solver import CommandResult, SolverStateSession, StatefulSolverLoop
from envsolve.state import EventStore, audit_state_artifacts


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _docker_json(*args: str) -> Any:
    process = subprocess.run(
        ["docker", *args],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or f"docker {' '.join(args)} failed")
    return json.loads(process.stdout)


def _image_identity(value: dict[str, Any]) -> ImageIdentity:
    return ImageIdentity(
        reference=str(value["reference"]),
        image_id=str(value.get("id", value.get("image_id"))),
        repo_digests=tuple(str(item) for item in value.get("repo_digests", [])),
    )


def _verify_file(root: Path, record: dict[str, Any], label: str) -> Path:
    path = root / str(record["path"])
    if not path.is_file() or _sha256(path) != record["sha256"]:
        raise ValueError(f"Preregistered source changed: {label}")
    return path


class DockerExecutor:
    def __init__(self, container: str, timeout_seconds: float = 600.0) -> None:
        self.container = container
        self.timeout_seconds = timeout_seconds
        self.commands: list[str] = []

    def execute(self, command: str) -> CommandResult:
        self.commands.append(command)
        started = time.monotonic()
        try:
            process = subprocess.run(
                ["docker", "exec", self.container, "bash", "-lc", command],
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            return CommandResult(
                exit_code=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
                duration_seconds=time.monotonic() - started,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else exc.stderr
            return CommandResult(
                exit_code=124,
                stdout=stdout or "",
                stderr=stderr or "P4D action timed out",
                duration_seconds=time.monotonic() - started,
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover and verify one typed system-capability repair."
    )
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    args = parser.parse_args()

    prereg_path = args.preregistration.resolve()
    output_root = args.output_root.resolve()
    summary_path = args.summary.resolve()
    event_log = output_root / "state.jsonl"
    snapshot = output_root / "snapshot.json"
    plan_path = output_root / "repair_plans.json"
    if output_root.exists() or summary_path.exists():
        raise FileExistsError("Refusing to overwrite a P4D validation artifact")

    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    if prereg.get("preregistration_id") != "p4d-capability-round1-v1":
        raise ValueError("Unexpected P4D preregistration identifier")
    sources = prereg["sources"]
    checked = {
        name: _verify_file(WORKSPACE_ROOT, record, name)
        for name, record in sources.items()
        if "path" in record
    }
    target = prereg["target"]
    p3_summary = json.loads(checked["p3_summary"].read_text(encoding="utf-8"))
    cases = [
        item
        for item in p3_summary["cases"]
        if item["repository"] == target["repository"]
        and item["revision"] == target["revision"]
    ]
    if len(cases) != 1:
        raise ValueError("Preregistered P3 target is not unique")
    p3_case = cases[0]
    p3_root = WORKSPACE_ROOT / sources["p3_state"]["root"]
    p3_event_log = p3_root / "state.jsonl"
    p3_snapshot = p3_root / "snapshot.json"
    if (
        _sha256(p3_event_log) != sources["p3_state"]["event_log_sha256"]
        or _sha256(p3_snapshot) != sources["p3_state"]["snapshot_sha256"]
    ):
        raise ValueError("Preregistered P3 state files changed")
    p3_audit = audit_state_artifacts(p3_event_log, p3_snapshot, target["case_id"])
    if (
        not p3_audit.valid
        or p3_audit.snapshot_hash != sources["p3_state"]["snapshot_hash"]
    ):
        raise ValueError("Preregistered P3 state failed audit")
    p3_conflicts = p3_case["report"]["conflicts"]
    if len(p3_conflicts) != 1 or p3_conflicts[0]["conflict_id"] != target["conflict_id"]:
        raise ValueError("Preregistered P3 conflict changed")
    if (
        p3_conflicts[0]["domain"] != target["domain"]
        or p3_conflicts[0]["subject"] != target["subject"]
    ):
        raise ValueError("Preregistered P3 conflict identity changed")

    manifest = json.loads(checked["original_manifest"].read_text(encoding="utf-8"))
    run_audit = json.loads(checked["original_audit"].read_text(encoding="utf-8"))
    if not run_audit.get("valid"):
        raise ValueError("Original target run audit is invalid")
    manifest_case = manifest["case"]
    if (
        manifest_case["repository"] != target["repository"]
        or manifest_case["revision"] != target["revision"]
    ):
        raise ValueError("Original manifest does not match the target")
    raw_result = json.loads(checked["raw_result"].read_text(encoding="utf-8"))
    if (
        raw_result["repo_name"] != target["repository"]
        or raw_result["commit_sha"] != target["revision"]
    ):
        raise ValueError("Original raw result does not match the target")
    target_image = _image_identity(manifest["evaluator"]["image"])

    context_summary = json.loads(checked["p4b_context"].read_text(encoding="utf-8"))
    source_image = _image_identity(context_summary["image"])
    prereg_image = _image_identity(prereg["image"])
    if source_image != target_image or source_image != prereg_image:
        raise ValueError("P4D source, target, and preregistered images do not match")
    local_image = _docker_json("image", "inspect", source_image.reference)[0]
    if local_image.get("Id") != source_image.image_id:
        raise ValueError("Local evaluator image identity changed")
    source_artifact = context_summary["artifact"]
    source_root = WORKSPACE_ROOT / source_artifact["root"]
    source_event_log = source_root / "state.jsonl"
    source_snapshot = source_root / "snapshot.json"
    source_audit = audit_state_artifacts(
        source_event_log,
        source_snapshot,
        source_artifact["case_id"],
    )
    if (
        not source_audit.valid
        or source_audit.snapshot_hash != source_artifact["snapshot_hash"]
        or _sha256(source_event_log) != source_artifact["event_log_sha256"]
        or _sha256(source_snapshot) != source_artifact["snapshot_sha256"]
    ):
        raise ValueError("P4B context artifact changed or failed audit")

    lineage = ContextTransferLineage(
        source_case_id=source_artifact["case_id"],
        source_snapshot_hash=source_artifact["snapshot_hash"],
        source_event_log_sha256=source_artifact["event_log_sha256"],
        source_summary_sha256=sources["p4b_context"]["sha256"],
        target_manifest_sha256=sources["original_manifest"]["sha256"],
        target_audit_sha256=sources["original_audit"]["sha256"],
        target_raw_result_path=sources["raw_result"]["path"],
        target_raw_result_sha256=sources["raw_result"]["sha256"],
    )

    output_root.mkdir(parents=True)
    shutil.copy2(p3_event_log, event_log)
    shutil.copy2(p3_snapshot, snapshot)
    session = SolverStateSession(event_log, snapshot, EventStore(event_log, target["case_id"]).reconstruct().case or {})
    source_state = EventStore(source_event_log, source_artifact["case_id"]).reconstruct()
    transfer = transfer_context_evidence(
        source_state,
        session,
        source_image,
        target_image,
        lineage,
    )

    container = f"envsolve-p4d-{uuid.uuid4().hex[:12]}"
    created = False
    executor: DockerExecutor | None = None
    discovery_result = None
    repair_results: list[dict[str, Any]] = []
    plans = ()
    try:
        create = subprocess.run(
            [
                "docker",
                "create",
                "--network",
                "bridge",
                "--name",
                container,
                source_image.reference,
                "sleep",
                "infinity",
            ],
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if create.returncode != 0:
            raise RuntimeError(create.stderr.strip() or "docker create failed")
        created = True
        container_record = _docker_json("inspect", container)[0]
        if container_record.get("Mounts"):
            raise ValueError("P4D validation container unexpectedly has mounts")
        if container_record.get("HostConfig", {}).get("NetworkMode") != "bridge":
            raise ValueError("P4D validation container network mode changed")
        start = subprocess.run(
            ["docker", "start", container],
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if start.returncode != 0:
            raise RuntimeError(start.stderr.strip() or "docker start failed")
        executor = DockerExecutor(container)
        discovery_result = StatefulSolverLoop(
            session,
            executor,
            max_actions=10,
            goal_id=f"goal-discovery-{target['subject']}",
            goal_description="Discover a package for a typed executable capability",
        ).run(AptFileDiscoveryPolicy(session, target["subject"]))

        engine = RepairConstraintEngine()
        if discovery_result.goal_status == "satisfied":
            context = build_repair_context(session.reconstruct()).context
            proposed = RepairRegistry().propose(session.reconstruct(), context, engine)
            plans = tuple(
                plan
                for plan in proposed
                if plan.kind == RepairKind.SYSTEM_CAPABILITY_INSTALL
            )
            if not plans:
                raise ValueError("Capability discovery produced no typed repair plan")
            if len(plans) > prereg["discovery"]["max_candidate_plans"]:
                raise ValueError("Capability repair candidates exceed preregistered budget")
            preflights = [
                preflight_repair(session.reconstruct(), plan, engine) for plan in plans
            ]
            if not all(item.allowed for item in preflights):
                raise ValueError("A discovered capability repair failed preflight")
            _write_json_atomic(
                plan_path,
                {
                    "schema_version": "1.0.0",
                    "preregistered_at": datetime.now(timezone.utc).isoformat(),
                    "preregistration_sha256": _sha256(prereg_path),
                    "repository": target["repository"],
                    "revision": target["revision"],
                    "context": context.to_dict(),
                    "plans": [plan.to_dict() for plan in plans],
                    "preflights": [item.to_dict() for item in preflights],
                },
            )
            for plan in plans:
                execution = StatefulSolverLoop(
                    session,
                    executor,
                    max_actions=3,
                    goal_id=f"goal-{plan.repair_id}",
                    goal_description="Verify a typed system-capability repair",
                ).run(TypedRepairPolicy(plan, session, engine))
                repair_results.append(
                    {"repair_id": plan.repair_id, "execution": execution.to_dict()}
                )
                if execution.goal_status == "satisfied":
                    break
    finally:
        if created:
            subprocess.run(
                ["docker", "rm", "-f", container],
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )

    derived_audit = audit_state_artifacts(event_log, snapshot, target["case_id"])
    if not derived_audit.valid:
        raise ValueError(f"P4D derived state audit failed: {derived_audit.errors}")
    final_state = session.reconstruct()
    post_report = RepairConstraintEngine().solve_state(final_state)
    satisfied_repair = next(
        (
            item
            for item in repair_results
            if item["execution"]["goal_status"] == "satisfied"
        ),
        None,
    )
    result = {
        "schema_version": "1.0.0",
        "validation_id": "p4d-capability-round1-v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "development_only": True,
        "preregistration": {
            "path": str(prereg_path.relative_to(WORKSPACE_ROOT)),
            "sha256": _sha256(prereg_path),
        },
        "repository": target["repository"],
        "revision": target["revision"],
        "target": target,
        "image": source_image.to_dict(),
        "lineage": lineage.to_dict(),
        "transfer": transfer.to_dict(),
        "discovery": discovery_result.to_dict() if discovery_result else None,
        "plans": [plan.to_dict() for plan in plans],
        "repair_results": repair_results,
        "commands": list(executor.commands if executor is not None else []),
        "post_state": post_report.to_dict(),
        "satisfied_repair_id": (
            satisfied_repair["repair_id"] if satisfied_repair is not None else None
        ),
        "superseded_constraint_ids": [
            constraint_id
            for plan in plans
            for constraint_id in plan.supersede_constraint_ids
            if final_state.constraints[constraint_id]["status"] == "superseded"
        ],
        "isolation": {
            "network": "bridge",
            "network_purpose": "apt provider and package acquisition",
            "repository_mounted": False,
            "mounts": [],
            "official_evaluation": False,
        },
        "artifact": {
            "root": str(output_root.relative_to(WORKSPACE_ROOT)),
            "case_id": target["case_id"],
            "event_count": derived_audit.event_count,
            "snapshot_hash": derived_audit.snapshot_hash,
            "event_log_sha256": _sha256(event_log),
            "snapshot_sha256": _sha256(snapshot),
            "plan_sha256": _sha256(plan_path) if plan_path.is_file() else None,
            "audit_valid": derived_audit.valid,
        },
        "integrity": prereg["integrity"],
    }
    _write_json_atomic(summary_path, result)
    print(
        json.dumps(
            {
                "discovery_status": (
                    discovery_result.goal_status if discovery_result else "not-run"
                ),
                "candidate_commands": [plan.mutation_command for plan in plans],
                "repair_satisfied": satisfied_repair is not None,
                "post_satisfiable": post_report.satisfiable,
                "superseded": result["superseded_constraint_ids"],
                "audit_valid": derived_audit.valid,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if satisfied_repair is not None and post_report.satisfiable else 1


if __name__ == "__main__":
    raise SystemExit(main())
