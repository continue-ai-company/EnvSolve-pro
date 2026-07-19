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
from envsolve.execution import (
    RuntimeExecutionContract,
    derive_runtime_execution_contract,
)
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


class DockerRepairExecutor:
    def __init__(
        self,
        container: str,
        runtime_contract: RuntimeExecutionContract,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.container = container
        self.runtime_contract = runtime_contract
        self.timeout_seconds = timeout_seconds
        self.commands: list[str] = []

    def execute(self, command: str) -> CommandResult:
        self.commands.append(command)
        started = time.monotonic()
        effective_command = self.runtime_contract.wrap(command)
        try:
            process = subprocess.run(
                [
                    "docker",
                    "exec",
                    self.container,
                    "bash",
                    "-lc",
                    effective_command,
                ],
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
                stderr=stderr or "repair action timed out",
                duration_seconds=time.monotonic() - started,
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Transfer image context and validate one runtime repair."
    )
    parser.add_argument("--repository", required=True)
    parser.add_argument("--p3-summary", required=True, type=Path)
    parser.add_argument("--context-summary", required=True, type=Path)
    parser.add_argument("--target-manifest", required=True, type=Path)
    parser.add_argument("--target-audit", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    args = parser.parse_args()

    p3_summary_path = args.p3_summary.resolve()
    context_summary_path = args.context_summary.resolve()
    target_manifest_path = args.target_manifest.resolve()
    target_audit_path = args.target_audit.resolve()
    output_root = args.output_root.resolve()
    event_log = output_root / "state.jsonl"
    snapshot = output_root / "snapshot.json"
    plan_path = output_root / "plan.json"
    if output_root.exists():
        raise FileExistsError(f"Refusing to overwrite P4C artifact: {output_root}")

    p3_summary = json.loads(p3_summary_path.read_text(encoding="utf-8"))
    matches = [
        item for item in p3_summary["cases"] if item["repository"] == args.repository
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one P3 case for {args.repository}, got {len(matches)}")
    p3_case = matches[0]
    p3_root = WORKSPACE_ROOT / p3_case["artifact_root"]
    p3_event_log = p3_root / "state.jsonl"
    p3_snapshot = p3_root / "snapshot.json"
    target_case_id = f"recorded-result:{args.repository}@{p3_case['revision']}"
    p3_audit = audit_state_artifacts(p3_event_log, p3_snapshot, target_case_id)
    if not p3_audit.valid or p3_audit.snapshot_hash != p3_case["snapshot_hash"]:
        raise ValueError("P3 target state failed lineage audit")
    raw_result = WORKSPACE_ROOT / p3_case["source"]
    if _sha256(raw_result) != p3_case["source_sha256"]:
        raise ValueError("P3 raw result source hash changed")

    manifest = json.loads(target_manifest_path.read_text(encoding="utf-8"))
    run_audit = json.loads(target_audit_path.read_text(encoding="utf-8"))
    if not run_audit.get("valid"):
        raise ValueError("Original target run audit is invalid")
    manifest_case = manifest.get("case", {})
    if (
        manifest_case.get("repository") != args.repository
        or manifest_case.get("revision") != p3_case["revision"]
    ):
        raise ValueError("Original run manifest case does not match P3 state")
    run_root = target_manifest_path.parent
    try:
        raw_result.relative_to(run_root)
    except ValueError as exc:
        raise ValueError("P3 raw result is outside the original target run") from exc
    raw_value = json.loads(raw_result.read_text(encoding="utf-8"))
    if (
        raw_value.get("repo_name") != args.repository
        or raw_value.get("commit_sha") != p3_case["revision"]
    ):
        raise ValueError("P3 raw result identity does not match target case")
    target_image = _image_identity(manifest["evaluator"]["image"])

    context_summary = json.loads(context_summary_path.read_text(encoding="utf-8"))
    if context_summary.get("validation_id") != "p4b-case-free-image-context-v1":
        raise ValueError("Unexpected context inventory validation identifier")
    source_image = _image_identity(context_summary["image"])
    if source_image != target_image:
        raise ValueError("Original case and context inventory images do not match")
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
    if not source_audit.valid or source_audit.snapshot_hash != source_artifact["snapshot_hash"]:
        raise ValueError("P4B context source failed lineage audit")
    if (
        _sha256(source_event_log) != source_artifact["event_log_sha256"]
        or _sha256(source_snapshot) != source_artifact["snapshot_sha256"]
    ):
        raise ValueError("P4B context source artifact hashes changed")

    lineage = ContextTransferLineage(
        source_case_id=source_artifact["case_id"],
        source_snapshot_hash=source_artifact["snapshot_hash"],
        source_event_log_sha256=source_artifact["event_log_sha256"],
        source_summary_sha256=_sha256(context_summary_path),
        target_manifest_sha256=_sha256(target_manifest_path),
        target_audit_sha256=_sha256(target_audit_path),
        target_raw_result_path=p3_case["source"],
        target_raw_result_sha256=p3_case["source_sha256"],
    )

    output_root.mkdir(parents=True)
    shutil.copy2(p3_event_log, event_log)
    shutil.copy2(p3_snapshot, snapshot)
    target_state = EventStore(event_log, target_case_id).reconstruct()
    session = SolverStateSession(event_log, snapshot, target_state.case or {})
    source_state = EventStore(source_event_log, source_artifact["case_id"]).reconstruct()
    transfer = transfer_context_evidence(
        source_state,
        session,
        source_image,
        target_image,
        lineage,
    )
    transferred_state = session.reconstruct()
    context = build_repair_context(transferred_state).context
    runtime_contract = derive_runtime_execution_contract(
        transferred_state,
        context,
    )
    engine = RepairConstraintEngine()
    plans = RepairRegistry().propose(session.reconstruct(), context, engine)
    runtime_plans = [
        plan for plan in plans if plan.kind == RepairKind.RUNTIME_SELECTION
    ]
    if len(runtime_plans) != 1:
        raise ValueError(f"Expected one runtime repair plan, got {len(runtime_plans)}")
    plan = runtime_plans[0]
    preflight = preflight_repair(session.reconstruct(), plan, engine)
    if not preflight.allowed:
        raise ValueError(f"Transferred runtime plan failed preflight: {preflight.reasons}")
    preregistration = {
        "schema_version": "1.0.0",
        "preregistered_at": datetime.now(timezone.utc).isoformat(),
        "repository": args.repository,
        "revision": p3_case["revision"],
        "lineage": lineage.to_dict(),
        "transfer": transfer.to_dict(),
        "context": context.to_dict(),
        "plan": plan.to_dict(),
        "preflight": preflight.to_dict(),
        "execution_scope": {
            "network": "none",
            "repository_mounted": False,
            "official_evaluation": False,
            "runtime_execution_contract": runtime_contract.to_dict(),
        },
    }
    _write_json_atomic(plan_path, preregistration)

    container = f"envsolve-p4c-{uuid.uuid4().hex[:12]}"
    created = False
    executor: DockerRepairExecutor | None = None
    try:
        create = subprocess.run(
            [
                "docker",
                "create",
                "--network",
                "none",
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
            raise ValueError("P4C runtime validation container unexpectedly has mounts")
        start = subprocess.run(
            ["docker", "start", container],
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if start.returncode != 0:
            raise RuntimeError(start.stderr.strip() or "docker start failed")
        executor = DockerRepairExecutor(container, runtime_contract)
        execution = StatefulSolverLoop(
            session,
            executor,
            max_actions=3,
            goal_id=f"goal-{plan.repair_id}",
            goal_description="Validate transferred-context runtime repair",
        ).run(TypedRepairPolicy(plan, session, engine))
    finally:
        if created:
            subprocess.run(
                ["docker", "rm", "-f", container],
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )

    derived_audit = audit_state_artifacts(event_log, snapshot, target_case_id)
    if not derived_audit.valid:
        raise ValueError(f"P4C derived state audit failed: {derived_audit.errors}")
    final_state = session.reconstruct()
    post_report = engine.solve_state(final_state)
    result = {
        "schema_version": "1.0.0",
        "validation_id": "p4c-neps-runtime-transfer-v2",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "development_only": True,
        "repository": args.repository,
        "revision": p3_case["revision"],
        "image": source_image.to_dict(),
        "lineage": lineage.to_dict(),
        "transfer": transfer.to_dict(),
        "context": context.to_dict(),
        "plan": plan.to_dict(),
        "preflight": preflight.to_dict(),
        "execution": execution.to_dict(),
        "commands": list(executor.commands if executor is not None else []),
        "runtime_execution_contract": runtime_contract.to_dict(),
        "post_state": post_report.to_dict(),
        "superseded_constraint_ids": [
            constraint_id
            for constraint_id in plan.supersede_constraint_ids
            if final_state.constraints[constraint_id]["status"] == "superseded"
        ],
        "isolation": {
            "network": "none",
            "repository_mounted": False,
            "mounts": [],
            "official_evaluation": False,
        },
        "artifact": {
            "root": str(output_root.relative_to(WORKSPACE_ROOT)),
            "case_id": target_case_id,
            "event_count": derived_audit.event_count,
            "snapshot_hash": derived_audit.snapshot_hash,
            "event_log_sha256": _sha256(event_log),
            "snapshot_sha256": _sha256(snapshot),
            "plan_sha256": _sha256(plan_path),
            "audit_valid": derived_audit.valid,
        },
        "integrity": {
            "model_requests": 0,
            "new_benchmark_executions": 0,
            "new_benchmark_cases": 0,
            "canary20_inspected": False,
            "official_test100_inspected": False,
        },
    }
    _write_json_atomic(args.summary.resolve(), result)
    print(
        json.dumps(
            {
                "goal_status": execution.goal_status,
                "selected_version": plan.proposed_fact.value,
                "commands": result["commands"],
                "post_satisfiable": post_report.satisfiable,
                "superseded": result["superseded_constraint_ids"],
                "audit_valid": derived_audit.valid,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if execution.goal_status == "satisfied" and post_report.satisfiable else 1


if __name__ == "__main__":
    raise SystemExit(main())
