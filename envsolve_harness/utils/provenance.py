from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
from typing import Any


def _git(path: Path, *args: str) -> str | None:
    try:
        process = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return process.stdout.strip() if process.returncode == 0 else None


def git_provenance(path: Path) -> dict[str, Any]:
    status = _git(path, "status", "--porcelain")
    return {
        "path": str(path.resolve()),
        "revision": _git(path, "rev-parse", "HEAD"),
        "dirty": bool(status) if status is not None else None,
        "status": status.splitlines() if status else [],
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(root: Path, paths: list[Path]) -> str:
    digest = hashlib.sha256()
    files: list[Path] = []
    for path in paths:
        files.extend(path.rglob("*") if path.is_dir() else [path])
    for path in sorted(item for item in files if item.is_file() and "__pycache__" not in item.parts):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def sha256_git_tracked_tree(root: Path, paths: list[Path]) -> str:
    """Hash current contents for tracked files under the selected source paths."""
    relative_paths: list[str] = []
    for path in paths:
        try:
            relative_paths.append(str(path.resolve().relative_to(root.resolve())))
        except ValueError as exc:
            raise ValueError(f"Source path is outside the Git root: {path}") from exc
    try:
        process = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--", *relative_paths],
            capture_output=True,
            check=False,
        )
    except OSError:
        return sha256_tree(root, paths)
    if process.returncode != 0:
        return sha256_tree(root, paths)

    digest = hashlib.sha256()
    stdout = process.stdout
    if isinstance(stdout, str):
        stdout = stdout.encode("utf-8", errors="surrogateescape")
    tracked = sorted(item for item in stdout.split(b"\0") if item)
    for encoded_path in tracked:
        relative = Path(encoded_path.decode("utf-8", errors="surrogateescape"))
        path = root / relative
        digest.update(encoded_path)
        digest.update(b"\0")
        if path.is_file():
            digest.update(bytes.fromhex(sha256_file(path)))
        else:
            digest.update(b"missing")
    return digest.hexdigest()


def host_provenance() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
    }


def docker_image_provenance(image: str) -> dict[str, Any]:
    try:
        process = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return {"reference": image, "inspect_error": f"{type(exc).__name__}: {exc}"}
    if process.returncode != 0:
        return {"reference": image, "inspect_error": process.stderr.strip()}
    inspected = json.loads(process.stdout)[0]
    return {
        "reference": image,
        "id": inspected.get("Id"),
        "repo_digests": inspected.get("RepoDigests", []),
    }
