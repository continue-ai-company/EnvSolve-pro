#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any


SCHEMA_VERSION = "1.0.0"
ROOT_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_roots(values: list[str]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for value in values:
        name, separator, raw_path = value.partition("=")
        if not separator or not ROOT_NAME.fullmatch(name):
            raise ValueError(f"Invalid cache root specification: {value!r}")
        path = Path(raw_path).expanduser().resolve()
        if name in roots:
            raise ValueError(f"Duplicate cache root name: {name}")
        if not path.is_dir():
            raise ValueError(f"Cache root is not a directory: {path}")
        roots[name] = path
    if not roots:
        raise ValueError("At least one --root is required")
    return roots


def _root_manifest(root: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    total_bytes = 0
    resolved_root = root.resolve()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            try:
                path.resolve().relative_to(resolved_root)
            except ValueError as error:
                raise ValueError(
                    f"Cache symlink escapes its root: {path}"
                ) from error
            entries.append(
                {
                    "path": relative,
                    "type": "symlink",
                    "target": path.readlink().as_posix(),
                }
            )
        elif path.is_file():
            size = path.stat().st_size
            total_bytes += size
            entries.append(
                {
                    "path": relative,
                    "type": "file",
                    "size_bytes": size,
                    "sha256": _sha256(path),
                }
            )
    return {
        "entries": entries,
        "entry_count": len(entries),
        "total_file_bytes": total_bytes,
    }


def build_manifest(roots: dict[str, Path], mode: str) -> dict[str, Any]:
    root_manifests = {
        name: _root_manifest(path) for name, path in sorted(roots.items())
    }
    identity = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "roots": root_manifests,
    }
    snapshot_id = hashlib.sha256(
        json.dumps(
            identity,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return {
        **identity,
        "snapshot_id": snapshot_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def verify_manifest(
    manifest: dict[str, Any],
    roots: dict[str, Path],
) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        return ["unsupported schema_version"]
    expected_roots = manifest.get("roots")
    if not isinstance(expected_roots, dict):
        return ["manifest roots must be an object"]
    if set(expected_roots) != set(roots):
        errors.append(
            "root names differ: "
            f"expected={sorted(expected_roots)} actual={sorted(roots)}"
        )
        return errors
    actual = build_manifest(roots, str(manifest.get("mode", "")))
    if actual["snapshot_id"] != manifest.get("snapshot_id"):
        errors.append(
            "snapshot_id mismatch: "
            f"expected={manifest.get('snapshot_id')} "
            f"actual={actual['snapshot_id']}"
        )
    for name in sorted(roots):
        if actual["roots"][name] != expected_roots[name]:
            errors.append(f"cache root differs: {name}")
    return errors


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
        description="Create or verify a content manifest for dependency caches."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    create.add_argument(
        "--mode",
        choices=("development", "frozen"),
        required=True,
    )
    create.add_argument("--services-stopped-acknowledged", action="store_true")
    create.add_argument("--root", action="append", default=[])
    create.add_argument("--output", type=Path, required=True)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--root", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    roots = _parse_roots(args.root)
    if args.command == "create":
        if args.mode == "frozen" and not args.services_stopped_acknowledged:
            raise ValueError(
                "Frozen snapshots require --services-stopped-acknowledged"
            )
        manifest = build_manifest(roots, args.mode)
        _write_json(args.output, manifest)
        print(
            f"snapshot_id={manifest['snapshot_id']} "
            f"roots={len(manifest['roots'])} output={args.output.resolve()}"
        )
        return 0

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    errors = verify_manifest(manifest, roots)
    if errors:
        for error in errors:
            print(f"error={error}")
        return 1
    print(
        f"verified=true snapshot_id={manifest['snapshot_id']} "
        f"roots={len(roots)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
