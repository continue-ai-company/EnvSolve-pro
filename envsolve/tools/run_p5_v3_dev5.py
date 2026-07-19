#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LABEL = "envsolve.p5"
SAFE_ARTIFACT = re.compile(r"^[A-Za-z0-9._-]+$")
SAFE_EXTRA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def require_hash(path: Path, expected: str) -> None:
    actual = sha_file(path)
    if actual != expected:
        raise ValueError(f"hash mismatch for {path}: {actual} != {expected}")


def pre_bootstrap_directory_script(prereg: dict[str, Any]) -> str:
    values = prereg.get("runner_contract", {}).get("pre_bootstrap_directories", [])
    if not isinstance(values, list):
        raise ValueError("pre_bootstrap_directories must be a list")
    if not all(
        isinstance(value, str)
        and SAFE_ARTIFACT.fullmatch(value)
        and len(PurePosixPath(value).parts) == 1
        and value not in {".", ".."}
        for value in values
    ):
        raise ValueError("pre_bootstrap_directories contains an unsafe path")
    directories = tuple(sorted(set(values)))
    lines = []
    for value in directories:
        lines.extend(
            [
                f"test ! -e {value} || {{ printf '%s\\n' 'pre-bootstrap artifact collides with repository path: {value}' >&2; exit 73; }}",
                f"mkdir -- {value}",
            ]
        )
    return "".join(line + "\n" for line in lines)


def verification_level(prereg: dict[str, Any]) -> str:
    value = prereg.get("verification_level", "V3")
    if value not in {"V1", "V3", "V4", "V6"}:
        raise ValueError(f"unsupported verification level: {value}")
    return value


def verifier_invocation(
    prereg: dict[str, Any], target: dict[str, Any]
) -> tuple[str, str, tuple[str, ...]]:
    level = verification_level(prereg)
    if level == "V3":
        return level, "envsolve/tools/run_p5_v3_in_container.py", ()
    if level == "V4":
        return level, "envsolve/tools/run_p5_v4_in_container.py", ()
    if level == "V6":
        return level, "envsolve/tools/run_p5_v6_in_container.py", ()
    plan = prereg.get("environment_plan", {})
    values = plan.get("selected_extras_by_bootstrap_sha256")
    if not isinstance(values, dict):
        raise ValueError("V1 requires selected extras keyed by bootstrap SHA256")
    bootstrap_sha256 = target["bootstrap"]["sha256"]
    if bootstrap_sha256 not in values:
        raise ValueError(f"selected extras missing for bootstrap {bootstrap_sha256}")
    extras = values[bootstrap_sha256]
    if not isinstance(extras, list) or not all(
        isinstance(extra, str) and SAFE_EXTRA.fullmatch(extra) for extra in extras
    ):
        raise ValueError("selected extras contain an invalid value")
    arguments = tuple(
        argument
        for extra in sorted(set(extras))
        for argument in ("--selected-extra", extra)
    )
    return level, "envsolve/tools/run_p5_v1_in_container.py", arguments


def validate_verifier_inputs(prereg: dict[str, Any]) -> None:
    if verification_level(prereg) != "V1":
        return
    values = prereg.get("environment_plan", {}).get(
        "selected_extras_by_bootstrap_sha256"
    )
    if not isinstance(values, dict):
        raise ValueError("V1 requires selected extras keyed by bootstrap SHA256")
    expected = {target["bootstrap"]["sha256"] for target in prereg["targets"]}
    if set(values) != expected:
        raise ValueError("selected extras must cover exactly the frozen bootstraps")
    for target in prereg["targets"]:
        verifier_invocation(prereg, target)


def implementation_manifest(level: str) -> dict[str, dict[str, str]]:
    paths = {
        "container_collector": f"envsolve/tools/run_p5_{level.lower()}_in_container.py",
        "network_isolation_policy": "envsolve/verification/network_isolation.py",
    }
    if level == "V1":
        paths.update(
            {
                "metadata_consistency_policy": "envsolve/verification/metadata_consistency.py",
                "metadata_snapshot_policy": "envsolve/verification/installed_metadata.py",
                "project_provenance_policy": "envsolve/verification/project_provenance.py",
            }
        )
    elif level == "V3":
        paths.update(
            {
                "metadata_snapshot_policy": "envsolve/verification/installed_metadata.py",
                "project_provenance_policy": "envsolve/verification/project_provenance.py",
                "smoke_policy": "envsolve/verification/smoke.py",
            }
        )
    else:
        if level == "V4":
            paths["native_project_policy"] = "envsolve/verification/native_project.py"
        else:
            paths.update(
                {
                    "environment_state_policy": "envsolve/verification/environment_state.py",
                    "metadata_snapshot_policy": "envsolve/verification/installed_metadata.py",
                    "project_provenance_policy": "envsolve/verification/project_provenance.py",
                    "replay_equivalence_policy": "envsolve/verification/replay_equivalence.py",
                }
            )
    return {
        name: {"path": path, "sha256": sha_file(ROOT / path)}
        for name, path in paths.items()
    }


def merge_preregistration(
    base: dict[str, Any], overlay: dict[str, Any]
) -> dict[str, Any]:
    inherited = overlay.get("base_preregistration", {}).get("inherit", [])
    merged = dict(overlay)
    for key in inherited:
        if key in overlay:
            raise ValueError(f"inherited preregistration field is overridden: {key}")
        if key not in base:
            raise ValueError(f"base preregistration field is missing: {key}")
        merged[key] = base[key]
    return merged


def load_preregistration(path: Path) -> dict[str, Any]:
    prereg = json.loads(path.read_text(encoding="utf-8"))
    base_value = prereg.get("base_preregistration")
    if not isinstance(base_value, dict):
        return prereg
    base_path = ROOT / base_value["path"]
    require_hash(base_path, base_value["sha256"])
    base = json.loads(base_path.read_text(encoding="utf-8"))
    return merge_preregistration(base, prereg)


def verify_frozen_preregistration_files(prereg: dict[str, Any]) -> None:
    for section_name in ("frozen_inputs", "frozen_observations", "frozen_policy_sources"):
        section = prereg.get(section_name, {})
        if not isinstance(section, dict):
            raise ValueError(f"invalid preregistration section: {section_name}")
        for item in section.values():
            if not isinstance(item, dict) or "path" not in item or "sha256" not in item:
                continue
            require_hash(ROOT / item["path"], item["sha256"])


def image_provenance(reference: str) -> dict[str, Any]:
    process = run(["docker", "image", "inspect", reference])
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip())
    values = json.loads(process.stdout)
    if len(values) != 1:
        raise RuntimeError("expected one Docker image")
    value = values[0]
    return {
        "reference": reference,
        "id": value["Id"],
        "repo_digests": sorted(value.get("RepoDigests") or []),
        "architecture": value.get("Architecture"),
        "os": value.get("Os"),
    }


def clean_archive(git_root: Path, revision: str, destination: Path) -> dict[str, str]:
    tree = run(["git", "-C", str(git_root), "rev-parse", f"{revision}^{{tree}}"])
    if tree.returncode != 0:
        raise RuntimeError(tree.stderr.strip())
    archive = destination.parent / "source.tar"
    process = run(
        ["git", "-C", str(git_root), "archive", "--format=tar", f"--output={archive}", revision]
    )
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip())
    destination.mkdir(parents=True)
    extract = run(["tar", "-xf", str(archive), "-C", str(destination)])
    if extract.returncode != 0:
        raise RuntimeError(extract.stderr.strip())
    result = {
        "source_materialization": "git_archive",
        "git_tree": tree.stdout.strip(),
        "archive_sha256": sha_file(archive),
    }
    archive.unlink()
    return result


def clean_checkout(git_root: Path, revision: str, destination: Path) -> dict[str, str]:
    clone = run(
        [
            "git",
            "clone",
            "--local",
            "--no-hardlinks",
            "--no-checkout",
            str(git_root),
            str(destination),
        ]
    )
    if clone.returncode != 0:
        raise RuntimeError(clone.stderr.strip())
    checkout = run(["git", "-C", str(destination), "checkout", "--detach", revision])
    if checkout.returncode != 0:
        raise RuntimeError(checkout.stderr.strip())
    head = run(["git", "-C", str(destination), "rev-parse", "HEAD"])
    tree = run(["git", "-C", str(destination), "rev-parse", "HEAD^{tree}"])
    status = run(
        [
            "git",
            "-C",
            str(destination),
            "status",
            "--porcelain",
            "--untracked-files=all",
        ]
    )
    if any(item.returncode != 0 for item in (head, tree, status)):
        raise RuntimeError("clean checkout provenance command failed")
    if head.stdout.strip() != revision:
        raise ValueError("clean checkout revision mismatch")
    if status.stdout:
        raise ValueError("clean checkout is dirty before bootstrap")
    return {
        "source_materialization": "detached_git_checkout",
        "head": head.stdout.strip(),
        "git_tree": tree.stdout.strip(),
        "pre_bootstrap_status_sha256": hashlib.sha256(status.stdout.encode()).hexdigest(),
    }


def materialize_source(
    git_root: Path,
    revision: str,
    destination: Path,
    mode: str,
) -> dict[str, str]:
    if mode == "git_archive":
        return clean_archive(git_root, revision, destination)
    if mode == "detached_git_checkout":
        return clean_checkout(git_root, revision, destination)
    raise ValueError(f"unknown source materialization: {mode}")


def container_networks(name: str) -> tuple[str, ...]:
    process = run(["docker", "inspect", name])
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip())
    values = json.loads(process.stdout)
    networks = values[0]["NetworkSettings"]["Networks"] or {}
    return tuple(sorted(networks))


def wait_for(path: Path, container: str, deadline: float) -> bool:
    while time.monotonic() < deadline:
        if path.exists():
            return True
        state = run(["docker", "inspect", "-f", "{{.State.Running}}", container])
        if state.returncode != 0 or state.stdout.strip() != "true":
            return path.exists()
        time.sleep(0.5)
    return False


def execute_target(
    target: dict[str, Any],
    prereg: dict[str, Any],
    image: dict[str, Any],
    output_root: Path,
    temporary_root: Path | None = None,
) -> dict[str, Any]:
    level, collector_path, collector_arguments = verifier_invocation(prereg, target)
    level_key = level.lower()
    slug = target["repository"].replace("/", "__")
    case_root = output_root / f"{slug}__{target['revision']}"
    case_root.mkdir(parents=True, exist_ok=False)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f"envsolve-p5-{level_key}-",
            dir=str(temporary_root) if temporary_root is not None else None,
        )
    )
    source = temporary / "source"
    control = temporary / "control"
    control.mkdir(parents=True)
    container = f"envsolve-p5-{level_key}-{slug.replace('_', '-')}-{os.getpid()}"
    started = time.monotonic()
    bootstrap_value = target["bootstrap"]
    bootstrap = ROOT / bootstrap_value["path"]
    require_hash(bootstrap, bootstrap_value["sha256"])
    source_mode = prereg["runner_contract"].get("source_materialization", "git_archive")
    provenance = materialize_source(
        ROOT / target["git_object_root"], target["revision"], source, source_mode
    )
    shutil.copyfile(bootstrap, control / "bootstrap.sh")
    wrapper = control / "wrapper.sh"
    git_safe_directory = (
        "git config --global --add safe.directory /data/project\n"
        if source_mode == "detached_git_checkout"
        else ""
    )
    artifact_setup = pre_bootstrap_directory_script(prereg)
    collector_argument_script = "".join(
        f" {shlex.quote(value)}" for value in collector_arguments
    )
    wrapper_script = (
        "#!/bin/bash\n"
        "cd /data/project\n"
        + git_safe_directory
        + "record_bootstrap_error() {\n"
        "  bootstrap_rc=$?\n"
        "  set +e\n"
        "  trap - ERR\n"
        "  printf '%s\\n' \"$bootstrap_rc\" > /envsolve-control/bootstrap.rc\n"
        "  touch /envsolve-control/bootstrap.done\n"
        "  exit \"$bootstrap_rc\"\n"
        "}\n"
        "trap record_bootstrap_error ERR\n"
        "set -e\n"
        + artifact_setup
        + "source /envsolve-control/bootstrap.sh > /envsolve-control/bootstrap.log 2>&1\n"
        "trap - ERR\n"
        "set +e\n"
        "printf '0\\n' > /envsolve-control/bootstrap.rc\n"
        "touch /envsolve-control/bootstrap.done\n"
        "while [ ! -f /envsolve-control/network.disabled ]; do sleep 0.2; done\n"
        f"python /opt/envsolve/{collector_path} "
        "--project-root /data/project "
        "--network-marker /envsolve-control/network.disabled "
        f"--output /envsolve-control/{level_key}.json"
        + collector_argument_script
        + f" > /envsolve-control/{level_key}.log 2>&1\n"
    )
    wrapper.write_text(wrapper_script, encoding="utf-8")
    wrapper.chmod(0o755)
    command = [
        "docker", "run", "-d", "--name", container,
        "--label", f"{LABEL}=true",
        "-v", f"{source}:/data/project",
        "-v", f"{control}:/envsolve-control",
        "-v", f"{ROOT / 'envsolve'}:/opt/envsolve/envsolve:ro",
        "-w", "/data/project",
        image["reference"],
        "bash", "/envsolve-control/wrapper.sh",
    ]
    container_id = None
    network_before: tuple[str, ...] = ()
    network_after: tuple[str, ...] = ()
    try:
        create = run(command, timeout=180)
        if create.returncode != 0:
            raise RuntimeError(create.stderr.strip())
        container_id = create.stdout.strip()
        print(f"[{target['repository']}] container started", flush=True)
        deadline = started + int(prereg["runner_contract"]["case_timeout_seconds"])
        if not wait_for(control / "bootstrap.done", container, deadline):
            raise TimeoutError("bootstrap marker timeout")
        bootstrap_rc = int((control / "bootstrap.rc").read_text().strip())
        print(f"[{target['repository']}] bootstrap exit {bootstrap_rc}", flush=True)
        if bootstrap_rc == 0:
            network_before = container_networks(container)
            for network in network_before:
                disconnected = run(["docker", "network", "disconnect", network, container])
                if disconnected.returncode != 0:
                    raise RuntimeError(disconnected.stderr.strip())
            network_after = container_networks(container)
            if network_after:
                raise RuntimeError("container network disconnect was incomplete")
            (control / "network.disabled").write_text("host-confirmed\n", encoding="utf-8")
            print(
                f"[{target['repository']}] network disabled; running {level}",
                flush=True,
            )
        remaining = max(1, int(deadline - time.monotonic()))
        waited = run(["docker", "wait", container], timeout=remaining)
        if waited.returncode != 0:
            raise RuntimeError(waited.stderr.strip())
        container_exit = int(waited.stdout.strip())
        verification = (
            json.loads((control / f"{level_key}.json").read_text(encoding="utf-8"))
            if (control / f"{level_key}.json").exists()
            else None
        )
        result = {
            "repository": target["repository"],
            "revision": target["revision"],
            "source": provenance,
            "bootstrap": {
                "path": bootstrap_value["path"],
                "sha256": bootstrap_value["sha256"],
                "exit_code": bootstrap_rc,
                "log_sha256": sha_file(control / "bootstrap.log"),
            },
            "container": {
                "id": container_id,
                "exit_code": container_exit,
                "networks_before_disconnect": list(network_before),
                "networks_after_disconnect": list(network_after),
            },
            level_key: verification,
            f"{level_key}_log_sha256": (
                sha_file(control / f"{level_key}.log")
                if (control / f"{level_key}.log").exists()
                else None
            ),
            "duration_seconds": time.monotonic() - started,
        }
        (case_root / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        shutil.copyfile(control / "bootstrap.log", case_root / "bootstrap.log")
        if (control / f"{level_key}.log").exists():
            shutil.copyfile(
                control / f"{level_key}.log", case_root / f"{level_key}.log"
            )
        return result
    finally:
        if container_id is not None:
            run(["docker", "rm", "-f", container])
        shutil.rmtree(temporary, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a preregistered P5 Dev-5 replay.")
    parser.add_argument(
        "--preregistration",
        type=Path,
        default=ROOT / "experiments/validations/p5_round4_v3_dev5_preregistration.json",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "runs/p5-v3-clean-dev5-round4-v1",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "experiments/validations/p5_round4_v3_dev5_results.json",
    )
    parser.add_argument("--network-change-confirmed", action="store_true")
    parser.add_argument(
        "--temporary-root",
        type=Path,
        help="Host directory for bind-mounted temporary case state.",
    )
    args = parser.parse_args()
    prereg_path = args.preregistration.resolve()
    prereg = load_preregistration(prereg_path)
    gate = prereg.get("execution_gate", {})
    if gate.get("requires_user_network_change_confirmation") and not args.network_change_confirmed:
        raise RuntimeError("network change confirmation is required before this replay")
    verify_frozen_preregistration_files(prereg)
    validate_verifier_inputs(prereg)
    level = verification_level(prereg)
    level_key = level.lower()
    image = image_provenance(prereg["environment"]["image_reference"])
    if image["id"] != prereg["environment"]["image_id"]:
        raise ValueError("Docker image ID changed")
    if prereg["environment"]["repo_digest"] not in image["repo_digests"]:
        raise ValueError("Docker repository digest changed")
    expected_os, expected_architecture = prereg["environment"]["platform"].split("/", 1)
    if image["os"] != expected_os or image["architecture"] != expected_architecture:
        raise ValueError("Docker image platform changed")
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    results = []
    for target in prereg["targets"]:
        results.append(
            execute_target(
                target,
                prereg,
                image,
                output_root,
                args.temporary_root.resolve() if args.temporary_root else None,
            )
        )
    aggregate = {
        "cases": len(results),
        "bootstrap_pass": sum(item["bootstrap"]["exit_code"] == 0 for item in results),
        f"{level_key}_pass": sum(
            item[level_key] is not None
            and item[level_key]["decision"]["passed"] is True
            for item in results
        ),
        f"{level_key}_fail": sum(
            item[level_key] is not None
            and item[level_key]["decision"]["passed"] is False
            for item in results
        ),
        f"{level_key}_unknown": sum(
            item[level_key] is None
            or item[level_key]["decision"]["passed"] is None
            for item in results
        ),
    }
    result = {
        "validation_id": prereg["preregistration_id"],
        "preregistration": {
            "path": str(prereg_path.relative_to(ROOT)),
            "sha256": sha_file(prereg_path),
        },
        "implementation": {
            "host_runner": {
                "path": str(Path(__file__).resolve().relative_to(ROOT)),
                "sha256": sha_file(Path(__file__).resolve()),
            },
            **implementation_manifest(level),
        },
        "image": image,
        "cases": results,
        "aggregate": aggregate,
        "integrity": {
            "model_requests": 0,
            "new_benchmark_executions": 0,
            "official_verifier_executions": 0,
            "retained_worktree_mutations": 0,
            "probe_network_requests": 0,
            "canary20_inspected": False,
            "official_test100_inspected": False,
            "official_score_modified": False,
        },
    }
    temporary_output = args.output.resolve().with_suffix(".tmp")
    temporary_output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary_output, args.output.resolve())
    print(args.output.resolve(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
