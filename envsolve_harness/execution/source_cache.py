from __future__ import annotations

import fcntl
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from envsolve_harness.core.io import read_json, write_json
from envsolve_harness.execution.process import checked_output
from envsolve_harness.storage.artifacts import safe_name


class ExactRevisionSourceCache:
    """Immutable Git-object cache with an independent checkout per episode."""

    cache_version = "immutable-exact-revision-cache-v1"

    def __init__(self, root: Path, timeout: int) -> None:
        if timeout <= 0:
            raise ValueError("Source-cache timeout must be positive")
        self.root = root.resolve()
        self.timeout = timeout

    def _cache_path(self, repository: str, revision: str) -> Path:
        return self.root / safe_name(repository) / f"{safe_name(revision)}.git"

    @staticmethod
    def _receipt_path(cache_path: Path) -> Path:
        return cache_path.with_suffix(".receipt.json")

    def _git(self, git_dir: Path, *arguments: str) -> str:
        return checked_output(
            ["git", "--git-dir", str(git_dir), *arguments],
            timeout=self.timeout,
        )

    def _identity(self, cache_path: Path) -> tuple[str, str]:
        commit = self._git(cache_path, "rev-parse", "refs/envsolve/exact^{commit}")
        tree = self._git(cache_path, "rev-parse", "refs/envsolve/exact^{tree}")
        return commit, tree

    def _validate_existing(
        self,
        cache_path: Path,
        repository: str,
        revision: str,
    ) -> dict[str, Any]:
        commit, tree = self._identity(cache_path)
        if commit != revision:
            raise RuntimeError(
                f"Source cache resolved {commit}, expected exact revision {revision}"
            )
        receipt_path = self._receipt_path(cache_path)
        if receipt_path.is_file():
            receipt = read_json(receipt_path)
            expected = {
                "cache_version": self.cache_version,
                "repository": repository,
                "revision": revision,
                "commit": commit,
                "tree": tree,
            }
            if any(receipt.get(key) != value for key, value in expected.items()):
                raise RuntimeError(f"Source-cache receipt mismatch: {receipt_path}")
        else:
            self._git(cache_path, "fsck", "--no-dangling")
            receipt = {
                "schema_version": "1.0.0",
                "cache_version": self.cache_version,
                "repository": repository,
                "revision": revision,
                "commit": commit,
                "tree": tree,
                "fsck": "pass",
            }
            write_json(receipt_path, receipt)
        return receipt

    def _populate(
        self,
        cache_path: Path,
        repository: str,
        revision: str,
        remote_url: str,
    ) -> dict[str, Any]:
        temporary = cache_path.parent / f".{cache_path.name}.tmp-{uuid.uuid4().hex}"
        try:
            checked_output(
                ["git", "init", "--bare", "-q", str(temporary)],
                timeout=self.timeout,
            )
            self._git(temporary, "remote", "add", "origin", remote_url)
            self._git(
                temporary,
                "fetch",
                "--depth",
                "1",
                "origin",
                revision,
            )
            fetched = self._git(temporary, "rev-parse", "FETCH_HEAD^{commit}")
            if fetched != revision:
                raise RuntimeError(f"Fetched {fetched}, expected exact revision {revision}")
            self._git(temporary, "update-ref", "refs/envsolve/exact", fetched)
            self._git(temporary, "update-ref", "refs/heads/envsolve-exact", fetched)
            self._git(
                temporary,
                "symbolic-ref",
                "HEAD",
                "refs/heads/envsolve-exact",
            )
            self._git(temporary, "fsck", "--no-dangling")
            os.replace(temporary, cache_path)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        return self._validate_existing(cache_path, repository, revision)

    def acquire(
        self,
        *,
        repository: str,
        revision: str,
        destination: Path,
        remote_url: str | None = None,
    ) -> dict[str, Any]:
        if destination.exists():
            raise FileExistsError(f"Source destination already exists: {destination}")
        cache_path = self._cache_path(repository, revision)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = cache_path.with_suffix(".lock")
        source_url = remote_url or f"https://github.com/{repository}.git"
        with lock_path.open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            cache_hit = cache_path.is_dir()
            receipt = (
                self._validate_existing(cache_path, repository, revision)
                if cache_hit
                else self._populate(cache_path, repository, revision, source_url)
            )

        checked_output(
            [
                "git",
                "clone",
                "--quiet",
                "--no-hardlinks",
                "--no-checkout",
                str(cache_path),
                str(destination),
            ],
            timeout=self.timeout,
        )
        checked_output(
            ["git", "checkout", "--quiet", "--detach", revision],
            cwd=destination,
            timeout=self.timeout,
        )
        checked_out = checked_output(
            ["git", "rev-parse", "HEAD"],
            cwd=destination,
            timeout=self.timeout,
        )
        if checked_out != revision:
            raise RuntimeError(f"Checked out {checked_out}, expected {revision}")
        return {
            "source": self.cache_version,
            "cache_hit": cache_hit,
            "cache_path": str(cache_path),
            "repository": repository,
            "revision": revision,
            "commit": receipt["commit"],
            "tree": receipt["tree"],
            "fsck": receipt["fsck"],
            "checkout": "independent-no-hardlinks",
        }
