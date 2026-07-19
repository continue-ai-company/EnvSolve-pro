#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from envsolve.context import build_repair_context
from envsolve.provenance import ContextTransferLineage, transfer_context_evidence
from envsolve.repairs import (
    RepairConstraintEngine,
    RepairKind,
    RepairRegistry,
    preflight_repair,
)
from envsolve.solver import ActionSpec, SolverStateSession, StatefulSolverLoop
from envsolve.state import EventStore, audit_state_artifacts
from envsolve.tools.run_p4d_capability_round2 import _verify_inputs
from envsolve.tools.run_p4d_capability_validation import (
    DockerExecutor,
    _docker_json,
    _sha256,
    _write_json_atomic,
)
from envsolve.verification import SemanticCapabilityRepairPolicy


def _load_checked(record: dict, label: str) -> tuple[Path, dict]:
    path = WORKSPACE_ROOT / record["path"]
    if _sha256(path) != record["sha256"]:
        raise ValueError(f"Round 3 input changed: {label}")
    return path, json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute the P4D Round 3 V2 repair.")
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    args = parser.parse_args()
    prereg_path = args.preregistration.resolve()
    output_root = args.output_root.resolve()
    summary_path = args.summary.resolve()
    if output_root.exists() or summary_path.exists():
        raise FileExistsError("Refusing to overwrite a Round 3 repair artifact")
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    if prereg.get("preregistration_id") != "p4d-capability-round3-repair-v1":
        raise ValueError("Unexpected Round 3 repair preregistration identifier")
    _, qualification = _load_checked(prereg["inputs"]["qualification"], "qualification")
    _, retry = _load_checked(prereg["inputs"]["retry"], "retry")
    round2_prereg_path, round2_prereg = _load_checked(
        prereg["inputs"]["round2_preregistration"],
        "round2 preregistration",
    )
    _load_checked(prereg["inputs"]["round3_preregistration"], "round3 preregistration")
    package = prereg["selected_package"]
    if retry.get("selected_package") != package or package in qualification.get(
        "qualified_packages", []
    ):
        raise ValueError("Selected package is not uniquely grounded by qualification retry")
    inputs = _verify_inputs(round2_prereg)
    target = inputs["target"]
    sources = inputs["sources"]
    image = inputs["source_image"]
    source_artifact = inputs["source_artifact"]
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
    event_log = output_root / "state.jsonl"
    snapshot = output_root / "snapshot.json"
    plan_path = output_root / "repair_plan.json"
    output_root.mkdir(parents=True)
    shutil.copy2(inputs["p3_event_log"], event_log)
    shutil.copy2(inputs["p3_snapshot"], snapshot)
    case = EventStore(event_log, target["case_id"]).reconstruct().case or {}
    session = SolverStateSession(event_log, snapshot, case)
    source_state = EventStore(
        inputs["source_event_log"], source_artifact["case_id"]
    ).reconstruct()
    transfer = transfer_context_evidence(
        source_state,
        session,
        image,
        inputs["target_image"],
        lineage,
    )
    qualification_evidence_id = "evidence-p4d-v2-qualified-capability-package"
    session.record_evidence(
        "context-capability-package-candidate",
        (
            "p4d-v2-qualification:"
            f"{prereg['inputs']['qualification']['sha256']}:"
            f"{prereg['inputs']['retry']['sha256']}"
        ),
        {
            "capability": target["subject"],
            "manager": "apt-get",
            "packages": [package],
        },
        evidence_id=qualification_evidence_id,
    )
    engine = RepairConstraintEngine()
    context = build_repair_context(session.reconstruct()).context
    plans = tuple(
        plan
        for plan in RepairRegistry().propose(session.reconstruct(), context, engine)
        if plan.kind == RepairKind.SYSTEM_CAPABILITY_INSTALL
    )
    if len(plans) != 1 or plans[0].mutation_command != f"apt-get install -y -- {package}":
        raise ValueError("V2 qualification did not produce exactly one grounded plan")
    plan = plans[0]
    preflight = preflight_repair(session.reconstruct(), plan, engine)
    if not preflight.allowed:
        raise ValueError("V2 capability plan failed transition preflight")
    _write_json_atomic(
        plan_path,
        {
            "schema_version": "1.0.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "preregistration_sha256": _sha256(prereg_path),
            "context": context.to_dict(),
            "plan": plan.to_dict(),
            "preflight": preflight.to_dict(),
        },
    )

    container = f"envsolve-p4d-r3repair-{uuid.uuid4().hex[:10]}"
    created = False
    executor = None
    execution = None
    try:
        create = subprocess.run(
            ["docker", "create", "--network", "bridge", "--name", container, image.reference, "sleep", "infinity"],
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if create.returncode != 0:
            raise RuntimeError(create.stderr.strip() or "docker create failed")
        created = True
        record = _docker_json("inspect", container)[0]
        if record.get("Mounts"):
            raise ValueError("Round 3 repair container unexpectedly has mounts")
        start = subprocess.run(
            ["docker", "start", container],
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if start.returncode != 0:
            raise RuntimeError(start.stderr.strip() or "docker start failed")
        executor = DockerExecutor(container, timeout_seconds=600.0)
        update = session.execute_action(
            ActionSpec(
                action_type="context_provider",
                command="apt-get update",
                rationale="Refresh apt metadata before the preregistered repair",
                action_id="p4d-round3-apt-update",
                metadata={"mutates_environment": True, "repair_action": False},
            ),
            executor,
        )
        if update.exit_code != 0:
            raise RuntimeError("Round 3 repair apt metadata update failed")
        execution = StatefulSolverLoop(
            session,
            executor,
            max_actions=4,
            goal_id=f"goal-v2-{plan.repair_id}",
            goal_description="Verify a semantic system-capability repair",
        ).run(
            SemanticCapabilityRepairPolicy(
                plan,
                session,
                f"{plan.proposed_fact.subject} --version",
                engine,
            )
        )
    finally:
        if created:
            subprocess.run(
                ["docker", "rm", "-f", container],
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
    audit = audit_state_artifacts(event_log, snapshot, target["case_id"])
    if not audit.valid:
        raise ValueError(f"Round 3 repair state audit failed: {audit.errors}")
    final_state = session.reconstruct()
    post = engine.solve_state(final_state)
    superseded = sorted(
        item
        for item in plan.supersede_constraint_ids
        if final_state.constraints[item]["status"] == "superseded"
    )
    result = {
        "schema_version": "1.0.0",
        "validation_id": "p4d-capability-round3-repair-v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "development_only": True,
        "preregistration_sha256": _sha256(prereg_path),
        "repository": target["repository"],
        "revision": target["revision"],
        "image": image.to_dict(),
        "lineage": lineage.to_dict(),
        "transfer": transfer.to_dict(),
        "qualification_evidence_id": qualification_evidence_id,
        "selected_package": package,
        "plan": plan.to_dict(),
        "preflight": preflight.to_dict(),
        "execution": execution.to_dict() if execution else None,
        "commands": executor.commands if executor else [],
        "post_state": post.to_dict(),
        "superseded_constraint_ids": superseded,
        "verifications": final_state.verifications,
        "isolation": {"network": "bridge", "repository_mounted": False, "mounts": []},
        "artifact": {
            "root": str(output_root.relative_to(WORKSPACE_ROOT)),
            "case_id": target["case_id"],
            "event_count": audit.event_count,
            "snapshot_hash": audit.snapshot_hash,
            "event_log_sha256": _sha256(event_log),
            "snapshot_sha256": _sha256(snapshot),
            "plan_sha256": _sha256(plan_path),
            "audit_valid": audit.valid,
        },
        "integrity": prereg["integrity"],
    }
    _write_json_atomic(summary_path, result)
    print(
        json.dumps(
            {
                "goal_status": execution.goal_status if execution else "not-run",
                "selected_package": package,
                "post_satisfiable": post.satisfiable,
                "superseded": superseded,
                "v2_passed": bool(final_state.verifications and final_state.verifications[-1]["passed"]),
                "audit_valid": audit.valid,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if execution and execution.goal_status == "satisfied" and post.satisfiable else 1


if __name__ == "__main__":
    raise SystemExit(main())
