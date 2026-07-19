#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from envsolve.tools.run_p5_v3_dev5 import (
    execute_target,
    image_provenance,
    load_preregistration,
    run,
    sha_file,
    validate_verifier_inputs,
    verification_level,
    verify_frozen_preregistration_files,
)
from envsolve.verification.replay_equivalence import (
    ReplayIdentity,
    ReplayObservation,
    compare_replays,
    snapshot_from_artifact,
)


def validate_image(prereg: dict[str, Any], image: dict[str, Any]) -> None:
    expected = prereg["environment"]
    if image["id"] != expected["image_id"]:
        raise ValueError("Docker image ID changed")
    if expected["repo_digest"] not in image["repo_digests"]:
        raise ValueError("Docker repository digest changed")
    expected_os, expected_architecture = expected["platform"].split("/", 1)
    if image["os"] != expected_os or image["architecture"] != expected_architecture:
        raise ValueError("Docker image platform changed")


def expected_tree(target: dict[str, Any]) -> str:
    process = run(
        [
            "git",
            "-C",
            str(ROOT / target["git_object_root"]),
            "rev-parse",
            f"{target['revision']}^{{tree}}",
        ]
    )
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip())
    return process.stdout.strip()


def replay_identity(
    prereg: dict[str, Any],
    preregistration_sha256: str,
    target: dict[str, Any],
    git_tree: str,
) -> ReplayIdentity:
    environment = prereg["environment"]
    return ReplayIdentity(
        image_id=environment["image_id"],
        repository_digest=environment["repo_digest"],
        platform=environment["platform"],
        repository=target["repository"],
        revision=target["revision"],
        git_tree=git_tree,
        bootstrap_sha256=target["bootstrap"]["sha256"],
        preregistration_sha256=preregistration_sha256,
    )


def collect_observation(
    identity: ReplayIdentity,
    replay: dict[str, Any] | None,
) -> tuple[ReplayObservation, tuple[dict[str, str], ...]]:
    if replay is None or replay.get("v6") is None:
        return ReplayObservation(identity, None), ()
    artifact = replay["v6"]
    errors = list(artifact.get("collection_errors") or ())
    source = replay.get("source", {})
    if (
        source.get("head") != identity.revision
        or source.get("git_tree") != identity.git_tree
        or source.get("pre_bootstrap_status_sha256")
        != hashlib.sha256(b"").hexdigest()
    ):
        errors.append(
            {
                "kind": "source-identity-invalid",
                "detail": "replay source identity or cleanliness evidence mismatched",
            }
        )
    if replay.get("container", {}).get("networks_after_disconnect") != []:
        errors.append(
            {
                "kind": "host-network-isolation-invalid",
                "detail": "container retained a Docker network during snapshot collection",
            }
        )
    if artifact.get("network") != {
        "host_disconnect_marker": True,
        "default_route_present": False,
    }:
        errors.append(
            {
                "kind": "container-network-isolation-invalid",
                "detail": "snapshot collector did not prove network isolation",
            }
        )
    errors_tuple = tuple(errors)
    if errors_tuple or artifact.get("snapshot") is None:
        return ReplayObservation(identity, None), errors_tuple
    try:
        snapshot = snapshot_from_artifact(artifact["snapshot"])
    except ValueError as exc:
        return (
            ReplayObservation(identity, None),
            ({"kind": "snapshot-invalid", "detail": str(exc)},),
        )
    return ReplayObservation(identity, snapshot), ()


def decision_dict(value: Any) -> dict[str, Any]:
    return {
        "passed": value.passed,
        "reason": value.reason,
        "first_snapshot_sha256": value.first_snapshot_sha256,
        "second_snapshot_sha256": value.second_snapshot_sha256,
        "differences": [item.__dict__ for item in value.differences],
    }


def replay_reference(
    replay: dict[str, Any] | None,
    error: dict[str, str] | None,
    result_path: Path,
) -> dict[str, Any]:
    if replay is None:
        return {"result": None, "execution_error": error}
    return {
        "result": {
            "path": str(result_path.relative_to(ROOT)),
            "sha256": sha_file(result_path),
        },
        "container_id": replay["container"]["id"],
        "bootstrap_exit_code": replay["bootstrap"]["exit_code"],
        "source": replay["source"],
        "snapshot_sha256": (
            replay["v6"]["snapshot"]["sha256"]
            if replay.get("v6") is not None and replay["v6"].get("snapshot") is not None
            else None
        ),
        "execution_error": error,
    }


def execute_replay(
    target: dict[str, Any],
    prereg: dict[str, Any],
    image: dict[str, Any],
    output_root: Path,
    temporary_root: Path | None,
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    try:
        return execute_target(target, prereg, image, output_root, temporary_root), None
    except (
        OSError,
        RuntimeError,
        TimeoutError,
        ValueError,
        subprocess.TimeoutExpired,
    ) as exc:
        return None, {"kind": type(exc).__name__, "detail": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run paired fresh-container P5 V6 replay.")
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--temporary-root", type=Path)
    args = parser.parse_args()

    preregistration_path = args.preregistration.resolve()
    prereg = load_preregistration(preregistration_path)
    verify_frozen_preregistration_files(prereg)
    validate_verifier_inputs(prereg)
    if verification_level(prereg) != "V6":
        raise ValueError("paired runner requires verification_level V6")
    preregistration_sha256 = sha_file(preregistration_path)
    image = image_provenance(prereg["environment"]["image_reference"])
    validate_image(prereg, image)

    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    replay_roots = (output_root / "replay-a", output_root / "replay-b")
    for root in replay_roots:
        root.mkdir()
    temporary_root = args.temporary_root.resolve() if args.temporary_root else None
    cases = []
    for target in prereg["targets"]:
        tree = expected_tree(target)
        identity = replay_identity(prereg, preregistration_sha256, target, tree)
        first, first_error = execute_replay(
            target, prereg, image, replay_roots[0], temporary_root
        )
        second, second_error = execute_replay(
            target, prereg, image, replay_roots[1], temporary_root
        )
        first_observation, first_collection_errors = collect_observation(identity, first)
        second_observation, second_collection_errors = collect_observation(identity, second)
        if (
            first is not None
            and second is not None
            and first["container"]["id"] == second["container"]["id"]
        ):
            second_observation = ReplayObservation(identity, None)
            second_collection_errors = second_collection_errors + (
                {
                    "kind": "container-identity-reused",
                    "detail": "paired replay did not receive a distinct container ID",
                },
            )
        decision = compare_replays(first_observation, second_observation)
        slug = target["repository"].replace("/", "__")
        dirname = f"{slug}__{target['revision']}"
        cases.append(
            {
                "repository": target["repository"],
                "revision": target["revision"],
                "identity": identity.__dict__,
                "replay_a": replay_reference(
                    first,
                    first_error,
                    replay_roots[0] / dirname / "result.json",
                ),
                "replay_b": replay_reference(
                    second,
                    second_error,
                    replay_roots[1] / dirname / "result.json",
                ),
                "collection_errors": {
                    "replay_a": list(first_collection_errors),
                    "replay_b": list(second_collection_errors),
                },
                "decision": decision_dict(decision),
            }
        )

    aggregate = {
        "cases": len(cases),
        "v6_pass": sum(case["decision"]["passed"] is True for case in cases),
        "v6_fail": sum(case["decision"]["passed"] is False for case in cases),
        "v6_unknown": sum(case["decision"]["passed"] is None for case in cases),
    }
    source_paths = {
        "paired_runner": "envsolve/tools/run_p5_v6_dev5.py",
        "host_runner": "envsolve/tools/run_p5_v3_dev5.py",
        "container_collector": "envsolve/tools/run_p5_v6_in_container.py",
        "environment_state_policy": "envsolve/verification/environment_state.py",
        "metadata_snapshot_policy": "envsolve/verification/installed_metadata.py",
        "project_provenance_policy": "envsolve/verification/project_provenance.py",
        "network_isolation_policy": "envsolve/verification/network_isolation.py",
        "replay_equivalence_policy": "envsolve/verification/replay_equivalence.py",
    }
    result = {
        "validation_id": prereg["preregistration_id"],
        "preregistration": {
            "path": str(preregistration_path.relative_to(ROOT)),
            "sha256": preregistration_sha256,
        },
        "implementation": {
            name: {"path": path, "sha256": sha_file(ROOT / path)}
            for name, path in source_paths.items()
        },
        "image": image,
        "cases": cases,
        "aggregate": aggregate,
        "integrity": {
            "fresh_replays_per_case": 2,
            "shared_writable_volumes_between_replays": 0,
            "model_requests": 0,
            "new_benchmark_executions": 0,
            "official_verifier_executions": 0,
            "retained_worktree_mutations": 0,
            "snapshot_network_requests": 0,
            "canary20_inspected": False,
            "official_test100_inspected": False,
            "official_score_modified": False,
        },
    }
    output = args.output.resolve()
    temporary_output = output.with_suffix(".tmp")
    temporary_output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary_output, output)
    print(output, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
