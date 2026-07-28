#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import time
from typing import Any
import urllib.request

if __package__:
    from .dependency_cache_snapshot import (
        build_manifest,
        verify_manifest,
    )
else:
    from dependency_cache_snapshot import build_manifest, verify_manifest


SCHEMA_VERSION = "1.0.0"
EPISODE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
ROOT_LAYOUT = {"pypi": "devpi", "apt": "apt"}
DEFAULT_COMPOSE_FILE = (
    Path(__file__).resolve().parents[1] / "dependency_cache" / "compose.yaml"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _parse_roots(values: list[str]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for value in values:
        name, separator, raw_path = value.partition("=")
        if not separator or name not in ROOT_LAYOUT or name in roots:
            raise ValueError(f"Invalid or duplicate seed root: {value!r}")
        path = Path(raw_path).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f"Seed root is not a directory: {path}")
        roots[name] = path
    if not roots:
        raise ValueError("At least one --seed-root is required")
    return roots


def _clone_tree(
    source: Path,
    destination: Path,
    *,
    strategy: str = "auto",
    system_name: str | None = None,
) -> str:
    if destination.exists():
        raise ValueError(f"Clone destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    system = system_name or platform.system()

    command: list[str] | None = None
    selected = "python-copytree"
    if strategy == "auto" and system == "Darwin":
        command = ["cp", "-cR", str(source), str(destination)]
        selected = "macos-clonefile"
    elif strategy == "auto" and system == "Linux":
        command = [
            "cp",
            "-a",
            "--reflink=auto",
            str(source),
            str(destination),
        ]
        selected = "linux-reflink-auto"
    elif strategy not in {"auto", "copy"}:
        raise ValueError(f"Unsupported clone strategy: {strategy}")

    if command is not None:
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
            return selected
        except subprocess.CalledProcessError:
            if destination.exists():
                shutil.rmtree(destination)

    shutil.copytree(source, destination, symlinks=True)
    return "python-copytree"


def _apt_proxy_config(endpoint: str) -> str:
    return "\n".join(
        [
            'Acquire::http::Proxy "DIRECT";',
            f'Acquire::http::Proxy::ports.ubuntu.com "{endpoint}";',
            f'Acquire::http::Proxy::archive.ubuntu.com "{endpoint}";',
            f'Acquire::http::Proxy::security.ubuntu.com "{endpoint}";',
            'Acquire::Queue-Mode "access";',
            'Acquire::http::Pipeline-Depth "0";',
            'Acquire::http::Timeout "120";',
            'Acquire::Retries "5";',
            "",
        ]
    )


def _default_bind_address() -> str:
    if platform.system() != "Linux":
        return "127.0.0.1"
    completed = subprocess.run(
        [
            "docker",
            "network",
            "inspect",
            "bridge",
            "--format",
            "{{(index .IPAM.Config 0).Gateway}}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    address = completed.stdout.strip()
    ipaddress.ip_address(address)
    return address


def prepare_episode(
    *,
    manifest_path: Path,
    seed_roots: dict[str, Path],
    episode_root: Path,
    episode_id: str,
    pypi_port: int = 3141,
    apt_port: int = 3142,
    bind_address: str | None = None,
    clone_strategy: str = "auto",
) -> dict[str, Any]:
    if not EPISODE_ID.fullmatch(episode_id):
        raise ValueError(f"Invalid episode ID: {episode_id!r}")
    if pypi_port == apt_port or not all(
        1 <= port <= 65535 for port in (pypi_port, apt_port)
    ):
        raise ValueError("Cache service ports must be distinct valid TCP ports")
    bind_address = bind_address or _default_bind_address()
    ipaddress.ip_address(bind_address)

    manifest_path = manifest_path.expanduser().resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("mode") != "frozen":
        raise ValueError("Episode seeds require a frozen cache manifest")
    if set(seed_roots) - set(ROOT_LAYOUT):
        raise ValueError("Episode seed contains unsupported cache roots")
    errors = verify_manifest(manifest, seed_roots)
    if errors:
        raise ValueError(f"Seed manifest verification failed: {errors}")

    episode_root = episode_root.expanduser().resolve()
    if episode_root.exists():
        raise ValueError(f"Episode root already exists: {episode_root}")
    cache_root = episode_root / "cache"
    metadata_root = episode_root / "metadata"
    cache_root.mkdir(parents=True)
    metadata_root.mkdir()

    started = time.monotonic()
    clone_strategies: dict[str, str] = {}
    runtime_seed_roots: dict[str, Path] = {}
    for name, source in sorted(seed_roots.items()):
        destination = cache_root / ROOT_LAYOUT[name]
        clone_strategies[name] = _clone_tree(
            source,
            destination,
            strategy=clone_strategy,
        )
        runtime_seed_roots[name] = destination
    for name, directory in ROOT_LAYOUT.items():
        if name not in runtime_seed_roots:
            (cache_root / directory).mkdir()
    (cache_root / "apt-logs").mkdir()

    copy_errors = verify_manifest(manifest, runtime_seed_roots)
    if copy_errors:
        raise ValueError(f"Runtime seed copy verification failed: {copy_errors}")

    endpoints = {
        "pypi": (
            f"http://host.docker.internal:{pypi_port}/root/pypi/+simple/"
        ),
        "apt": f"http://host.docker.internal:{apt_port}",
    }
    apt_config_path = metadata_root / "01envsolve-dependency-cache"
    apt_config_path.write_text(
        _apt_proxy_config(endpoints["apt"]),
        encoding="utf-8",
    )
    lease = {
        "schema_version": SCHEMA_VERSION,
        "state": "prepared",
        "episode_id": episode_id,
        "project_name": f"envsolve-cache-{episode_id}",
        "mode": "isolated-seeded",
        "upstream_miss_policy": "allow",
        "created_at": _utc_now(),
        "episode_root": str(episode_root),
        "cache_data_root": str(cache_root),
        "seed": {
            "manifest_path": str(manifest_path),
            "manifest_sha256": _sha256(manifest_path),
            "snapshot_id": manifest["snapshot_id"],
            "roots": {
                name: str(path) for name, path in sorted(seed_roots.items())
            },
        },
        "runtime_seed_roots": {
            name: str(path)
            for name, path in sorted(runtime_seed_roots.items())
        },
        "clone": {
            "strategies": clone_strategies,
            "duration_seconds": round(time.monotonic() - started, 6),
        },
        "ports": {"pypi": pypi_port, "apt": apt_port},
        "bind_address": bind_address,
        "endpoints": endpoints,
        "client": {
            "environment": {
                "PIP_INDEX_URL": endpoints["pypi"],
                "PIP_TRUSTED_HOST": "host.docker.internal",
            },
            "docker_run_args": [
                "--add-host=host.docker.internal:host-gateway"
            ],
            "apt_config_path": str(apt_config_path),
        },
    }
    _write_json(metadata_root / "lease.json", lease)
    return lease


def _validate_attestation(
    *,
    attestation_path: Path,
    lease: dict[str, Any],
    image_refs: dict[str, str],
) -> dict[str, Any]:
    attestation_path = attestation_path.expanduser().resolve()
    attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    expected = {
        "cache_mode": "isolated-seeded",
        "upstream_miss_policy": "allow",
        "cache_manifest_sha256": lease["seed"]["manifest_sha256"],
        "cache_snapshot_id": lease["seed"]["snapshot_id"],
        "endpoints": lease["endpoints"],
    }
    for name, value in expected.items():
        if attestation.get(name) != value:
            raise ValueError(
                f"Attestation field {name!r} differs from episode lease"
            )
    for role, image_ref in sorted(image_refs.items()):
        image = attestation.get("images", {}).get(role, {})
        if image.get("input_ref") != image_ref:
            raise ValueError(f"Attested image reference differs for {role}")
        completed = subprocess.run(
            ["docker", "image", "inspect", image_ref],
            check=True,
            capture_output=True,
            text=True,
        )
        records = json.loads(completed.stdout)
        if len(records) != 1 or records[0].get("Id") != image.get("image_id"):
            raise ValueError(f"Attested image identity differs for {role}")
    return {
        "path": str(attestation_path),
        "sha256": _sha256(attestation_path),
        "attestation_id": attestation["attestation_id"],
        "image_ids": {
            role: attestation["images"][role]["image_id"]
            for role in sorted(image_refs)
        },
    }


def _compose_environment(
    lease: dict[str, Any],
    *,
    image_tag: str,
) -> dict[str, str]:
    return {
        **os.environ,
        "ENVSOLVE_CACHE_DATA_ROOT": lease["cache_data_root"],
        "ENVSOLVE_CACHE_IMAGE_TAG": image_tag,
        "ENVSOLVE_CACHE_OFFLINE": "0",
        "ENVSOLVE_CACHE_BIND_ADDRESS": lease["bind_address"],
        "ENVSOLVE_CACHE_PYPI_PORT": str(lease["ports"]["pypi"]),
        "ENVSOLVE_CACHE_APT_PORT": str(lease["ports"]["apt"]),
    }


def _compose_command(
    lease: dict[str, Any],
    compose_file: Path,
) -> list[str]:
    return [
        "docker",
        "compose",
        "-p",
        lease["project_name"],
        "-f",
        str(compose_file),
    ]


def _wait_until_ready(lease: dict[str, Any], timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    bind_address = lease["bind_address"]
    pypi_url = (
        f"http://{bind_address}:{lease['ports']['pypi']}/+status"
    )
    apt_address = (bind_address, lease["ports"]["apt"])
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(pypi_url, timeout=3) as response:
                if response.status != 200:
                    raise RuntimeError(
                        f"DevPI health returned HTTP {response.status}"
                    )
            with socket.create_connection(apt_address, timeout=3):
                return
        except Exception as error:
            last_error = error
            time.sleep(2)
    raise TimeoutError(f"Cache services did not become ready: {last_error}")


def _verify_running_service_images(
    *,
    lease: dict[str, Any],
    command: list[str],
    environment: dict[str, str],
) -> None:
    for service, role in (("pypi", "pypi-service"), ("apt", "apt-service")):
        container = subprocess.run(
            [*command, "ps", "-q", service],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        ).stdout.strip()
        if not container:
            raise ValueError(f"Cache service has no running container: {service}")
        image_id = subprocess.run(
            ["docker", "inspect", "--format", "{{.Image}}", container],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        expected = lease["attestation"]["image_ids"][role]
        if image_id != expected:
            raise ValueError(
                f"Running service image differs from attestation: {service}"
            )


def summarize_service_logs(logs: str) -> dict[str, int]:
    return {
        "pypi_remote_reads": logs.count("reading remote:"),
        "pypi_project_gets": len(
            re.findall(r"GET /root/pypi/\+simple/", logs)
        ),
        "pypi_file_gets": len(re.findall(r"GET /root/pypi/\+f/", logs)),
        "upstream_timeouts": logs.count("getting data timed out"),
    }


def _capture_service_evidence(
    *,
    lease_path: Path,
    lease: dict[str, Any],
    command: list[str],
    environment: dict[str, str],
) -> None:
    completed = subprocess.run(
        [*command, "logs", "--no-color", "--timestamps"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    log_path = lease_path.parent / "service-logs.txt"
    log_path.write_text(completed.stdout, encoding="utf-8")
    lease["service_evidence"] = {
        "captured_at": _utc_now(),
        "log_path": str(log_path),
        "log_sha256": _sha256(log_path),
        "log_bytes": log_path.stat().st_size,
        "summary": summarize_service_logs(completed.stdout),
    }
    _write_json(lease_path, lease)


def open_episode(
    *,
    lease_path: Path,
    attestation_path: Path,
    compose_file: Path,
    image_tag: str,
    client_image: str,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    lease_path = lease_path.expanduser().resolve()
    lease = json.loads(lease_path.read_text(encoding="utf-8"))
    if lease.get("state") != "prepared":
        raise ValueError("Only a prepared episode can be opened")
    image_refs = {
        "pypi-service": f"envsolve/dependency-cache-pypi:{image_tag}",
        "apt-service": f"envsolve/dependency-cache-apt:{image_tag}",
        "client": client_image,
    }
    lease["attestation"] = _validate_attestation(
        attestation_path=attestation_path,
        lease=lease,
        image_refs=image_refs,
    )
    compose_file = compose_file.expanduser().resolve()
    command = _compose_command(lease, compose_file)
    environment = _compose_environment(lease, image_tag=image_tag)
    try:
        subprocess.run(
            [*command, "up", "-d", "--no-build"],
            check=True,
            env=environment,
        )
        _wait_until_ready(lease, timeout_seconds)
        _verify_running_service_images(
            lease=lease,
            command=command,
            environment=environment,
        )
    except Exception:
        subprocess.run(
            [*command, "down", "--remove-orphans"],
            check=False,
            env=environment,
        )
        raise
    lease["state"] = "running"
    lease["started_at"] = _utc_now()
    lease["compose_file"] = str(compose_file)
    lease["image_tag"] = image_tag
    lease["client_image"] = client_image
    _write_json(lease_path, lease)
    return lease


def finalize_episode(
    *,
    lease_path: Path,
    services_stopped: bool,
) -> dict[str, Any]:
    if not services_stopped:
        raise ValueError("Finalization requires stopped cache services")
    lease_path = lease_path.expanduser().resolve()
    lease = json.loads(lease_path.read_text(encoding="utf-8"))
    manifest_path = Path(lease["seed"]["manifest_path"])
    actual_manifest_sha256 = _sha256(manifest_path)
    if actual_manifest_sha256 != lease["seed"]["manifest_sha256"]:
        lease["state"] = "seed-integrity-failed"
        lease["closed_at"] = _utc_now()
        lease["seed_integrity_errors"] = ["seed manifest file changed"]
        _write_json(lease_path, lease)
        raise ValueError("Seed manifest file changed during episode")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    seed_roots = {
        name: Path(path) for name, path in lease["seed"]["roots"].items()
    }
    source_errors = verify_manifest(manifest, seed_roots)
    if source_errors:
        lease["state"] = "seed-integrity-failed"
        lease["closed_at"] = _utc_now()
        lease["seed_integrity_errors"] = source_errors
        _write_json(lease_path, lease)
        raise ValueError(f"Seed changed during episode: {source_errors}")

    runtime_roots = {
        name: Path(path)
        for name, path in lease["runtime_seed_roots"].items()
    }
    final_manifest = build_manifest(runtime_roots, "development")
    final_manifest_path = lease_path.parent / "final-cache-manifest.json"
    _write_json(final_manifest_path, final_manifest)
    initial_roots = manifest["roots"]
    final_roots = final_manifest["roots"]
    root_deltas = {
        name: {
            "entry_count": (
                final_roots[name]["entry_count"]
                - initial_roots[name]["entry_count"]
            ),
            "total_file_bytes": (
                final_roots[name]["total_file_bytes"]
                - initial_roots[name]["total_file_bytes"]
            ),
        }
        for name in sorted(runtime_roots)
    }
    lease["state"] = "closed"
    lease["closed_at"] = _utc_now()
    lease["seed_integrity_verified"] = True
    lease["final_cache"] = {
        "manifest_path": str(final_manifest_path),
        "manifest_sha256": _sha256(final_manifest_path),
        "snapshot_id": final_manifest["snapshot_id"],
        "changed_from_seed": (
            final_manifest["snapshot_id"] != manifest["snapshot_id"]
        ),
        "root_deltas": root_deltas,
    }
    _write_json(lease_path, lease)
    return lease


def _normalize_runtime_ownership(
    *,
    lease: dict[str, Any],
    environment: dict[str, str],
) -> dict[str, Any] | None:
    if platform.system() != "Linux":
        return None
    uid = os.getuid()
    gid = os.getgid()
    image = (
        "envsolve/dependency-cache-apt:"
        f"{environment['ENVSOLVE_CACHE_IMAGE_TAG']}"
    )
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--entrypoint",
            "/bin/chown",
            "--mount",
            (
                "type=bind,"
                f"src={lease['cache_data_root']},"
                "dst=/cache"
            ),
            image,
            "-R",
            f"{uid}:{gid}",
            "/cache",
        ],
        check=True,
        env=environment,
    )
    return {
        "normalized": True,
        "uid": uid,
        "gid": gid,
        "image": image,
        "completed_at": _utc_now(),
    }


def close_episode(
    *,
    lease_path: Path,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    lease_path = lease_path.expanduser().resolve()
    lease = json.loads(lease_path.read_text(encoding="utf-8"))
    if lease.get("state") != "running":
        raise ValueError("Only a running episode can be closed")
    compose_file = Path(lease["compose_file"])
    command = _compose_command(lease, compose_file)
    environment = _compose_environment(
        lease,
        image_tag=lease["image_tag"],
    )
    _capture_service_evidence(
        lease_path=lease_path,
        lease=lease,
        command=command,
        environment=environment,
    )
    subprocess.run(
        [
            *command,
            "down",
            "--remove-orphans",
            "--timeout",
            str(timeout_seconds),
        ],
        check=True,
        env=environment,
    )
    ownership = _normalize_runtime_ownership(
        lease=lease,
        environment=environment,
    )
    if ownership is not None:
        lease = json.loads(lease_path.read_text(encoding="utf-8"))
        lease["runtime_ownership"] = ownership
        _write_json(lease_path, lease)
    return finalize_episode(
        lease_path=lease_path,
        services_stopped=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Manage an isolated writable dependency-cache copy for one episode."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--manifest", type=Path, required=True)
    prepare.add_argument("--seed-root", action="append", default=[])
    prepare.add_argument("--episode-root", type=Path, required=True)
    prepare.add_argument("--episode-id", required=True)
    prepare.add_argument("--pypi-port", type=int, default=3141)
    prepare.add_argument("--apt-port", type=int, default=3142)
    prepare.add_argument("--bind-address")
    prepare.add_argument(
        "--clone-strategy",
        choices=("auto", "copy"),
        default="auto",
    )

    open_parser = subparsers.add_parser("open")
    open_parser.add_argument("--lease", type=Path, required=True)
    open_parser.add_argument("--attestation", type=Path, required=True)
    open_parser.add_argument(
        "--compose-file",
        type=Path,
        default=DEFAULT_COMPOSE_FILE,
    )
    open_parser.add_argument("--image-tag", required=True)
    open_parser.add_argument("--client-image", required=True)
    open_parser.add_argument("--timeout-seconds", type=int, default=180)

    close = subparsers.add_parser("close")
    close.add_argument("--lease", type=Path, required=True)
    close.add_argument("--timeout-seconds", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "prepare":
        lease = prepare_episode(
            manifest_path=args.manifest,
            seed_roots=_parse_roots(args.seed_root),
            episode_root=args.episode_root,
            episode_id=args.episode_id,
            pypi_port=args.pypi_port,
            apt_port=args.apt_port,
            bind_address=args.bind_address,
            clone_strategy=args.clone_strategy,
        )
    elif args.command == "open":
        lease = open_episode(
            lease_path=args.lease,
            attestation_path=args.attestation,
            compose_file=args.compose_file,
            image_tag=args.image_tag,
            client_image=args.client_image,
            timeout_seconds=args.timeout_seconds,
        )
    else:
        lease = close_episode(
            lease_path=args.lease,
            timeout_seconds=args.timeout_seconds,
        )
    print(
        f"episode_id={lease['episode_id']} state={lease['state']} "
        f"episode_root={lease['episode_root']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
