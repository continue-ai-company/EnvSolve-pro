#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


SCHEMA_VERSION = "1.0.0"
ASSIGNMENT_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")
REQUIRED_IMAGE_ROLES = {"pypi-service", "apt-service", "client"}
REQUIRED_ENDPOINTS = {"pypi", "apt"}
LABEL_PREFIX = "org.envsolve.dependency-cache."
VALID_SETTINGS = {
    ("mutable-shared", "allow"),
    ("isolated-seeded", "allow"),
    ("frozen-offline", "deny"),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_assignments(
    values: list[str],
    *,
    expected: set[str],
    kind: str,
) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for value in values:
        name, separator, assigned_value = value.partition("=")
        if (
            not separator
            or not ASSIGNMENT_NAME.fullmatch(name)
            or not assigned_value
        ):
            raise ValueError(f"Invalid {kind} assignment: {value!r}")
        if name in assignments:
            raise ValueError(f"Duplicate {kind} assignment: {name}")
        assignments[name] = assigned_value
    if set(assignments) != expected:
        raise ValueError(
            f"{kind} names differ: "
            f"expected={sorted(expected)} actual={sorted(assignments)}"
        )
    return assignments


def inspect_images(image_refs: dict[str, str]) -> dict[str, dict[str, Any]]:
    inspected: dict[str, dict[str, Any]] = {}
    for role, image_ref in sorted(image_refs.items()):
        completed = subprocess.run(
            ["docker", "image", "inspect", image_ref],
            check=True,
            capture_output=True,
            text=True,
        )
        records = json.loads(completed.stdout)
        if len(records) != 1:
            raise ValueError(
                f"Expected one Docker image for {image_ref!r}, got {len(records)}"
            )
        record = records[0]
        labels = record.get("Config", {}).get("Labels") or {}
        inspected[role] = {
            "input_ref": image_ref,
            "image_id": record["Id"],
            "repo_digests": sorted(record.get("RepoDigests") or []),
            "os": record.get("Os"),
            "architecture": record.get("Architecture"),
            "labels": {
                name: value
                for name, value in sorted(labels.items())
                if name.startswith(LABEL_PREFIX)
            },
        }
    return inspected


def _require_label(
    image: dict[str, Any],
    name: str,
    expected: str,
) -> None:
    actual = image.get("labels", {}).get(f"{LABEL_PREFIX}{name}")
    if actual != expected:
        raise ValueError(
            f"Image label {name!r} differs: "
            f"expected={expected!r} actual={actual!r}"
        )


def build_attestation(
    *,
    manifest: dict[str, Any],
    manifest_sha256: str,
    images: dict[str, dict[str, Any]],
    endpoints: dict[str, str],
    cache_mode: str,
    upstream_miss_policy: str,
) -> dict[str, Any]:
    if (cache_mode, upstream_miss_policy) not in VALID_SETTINGS:
        raise ValueError(
            "Invalid cache setting: "
            f"mode={cache_mode!r} "
            f"upstream_miss_policy={upstream_miss_policy!r}"
        )
    if set(images) != REQUIRED_IMAGE_ROLES:
        raise ValueError("Attestation requires pypi-service, apt-service, and client")
    if set(endpoints) != REQUIRED_ENDPOINTS:
        raise ValueError("Attestation requires pypi and apt endpoints")

    snapshot_id = manifest.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise ValueError("Cache manifest has no snapshot_id")
    expected_manifest_mode = (
        "development" if cache_mode == "mutable-shared" else "frozen"
    )
    if manifest.get("mode") != expected_manifest_mode:
        raise ValueError(
            "Cache manifest mode differs: "
            f"expected={expected_manifest_mode!r} "
            f"actual={manifest.get('mode')!r}"
        )

    for role in ("pypi-service", "apt-service", "client"):
        _require_label(images[role], "role", role)
    client = images["client"]
    _require_label(client, "snapshot", snapshot_id)
    _require_label(client, "mode", cache_mode)
    _require_label(client, "upstream-miss-policy", upstream_miss_policy)
    _require_label(client, "pypi", endpoints["pypi"])
    _require_label(client, "apt", endpoints["apt"])

    identity = {
        "schema_version": SCHEMA_VERSION,
        "cache_mode": cache_mode,
        "upstream_miss_policy": upstream_miss_policy,
        "cache_manifest_sha256": manifest_sha256,
        "cache_snapshot_id": snapshot_id,
        "images": images,
        "endpoints": dict(sorted(endpoints.items())),
    }
    attestation_id = hashlib.sha256(
        json.dumps(
            identity,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return {
        **identity,
        "attestation_id": attestation_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bind dependency-cache state and Docker image identities."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--cache-mode",
        choices=("mutable-shared", "isolated-seeded", "frozen-offline"),
        required=True,
    )
    parser.add_argument(
        "--upstream-miss-policy",
        choices=("allow", "deny"),
        required=True,
    )
    parser.add_argument("--image", action="append", default=[])
    parser.add_argument("--endpoint", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    image_refs = _parse_assignments(
        args.image,
        expected=REQUIRED_IMAGE_ROLES,
        kind="image",
    )
    endpoints = _parse_assignments(
        args.endpoint,
        expected=REQUIRED_ENDPOINTS,
        kind="endpoint",
    )
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    attestation = build_attestation(
        manifest=manifest,
        manifest_sha256=_sha256(manifest_path),
        images=inspect_images(image_refs),
        endpoints=endpoints,
        cache_mode=args.cache_mode,
        upstream_miss_policy=args.upstream_miss_policy,
    )
    _write_json(args.output, attestation)
    print(
        f"attestation_id={attestation['attestation_id']} "
        f"snapshot_id={attestation['cache_snapshot_id']} "
        f"output={args.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
