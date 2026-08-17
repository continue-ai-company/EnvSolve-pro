from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

from envsolve_harness.execution.process import checked_output
from envsolve_harness.execution.source_cache import ExactRevisionSourceCache


def _make_repository(root: Path) -> tuple[Path, str]:
    repository = root / "remote"
    checked_output(["git", "init", "-q", str(repository)], timeout=10)
    checked_output(
        ["git", "config", "user.email", "envsolve@example.test"],
        cwd=repository,
        timeout=10,
    )
    checked_output(
        ["git", "config", "user.name", "EnvSolve Test"],
        cwd=repository,
        timeout=10,
    )
    (repository / "value.txt").write_text("frozen\n", encoding="utf-8")
    checked_output(["git", "add", "value.txt"], cwd=repository, timeout=10)
    checked_output(["git", "commit", "-q", "-m", "frozen"], cwd=repository, timeout=10)
    revision = checked_output(["git", "rev-parse", "HEAD"], cwd=repository, timeout=10)
    return repository, revision


def test_exact_revision_cache_reuses_git_objects_but_not_worktree_state() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        remote, revision = _make_repository(root)
        cache = ExactRevisionSourceCache(root / "cache", timeout=10)

        first = cache.acquire(
            repository="owner/repository",
            revision=revision,
            destination=root / "first",
            remote_url=str(remote),
        )
        (root / "first" / "value.txt").write_text("agent state\n", encoding="utf-8")
        (root / "first" / "untracked.txt").write_text("private\n", encoding="utf-8")
        second = cache.acquire(
            repository="owner/repository",
            revision=revision,
            destination=root / "second",
            remote_url=str(remote),
        )

        assert first["cache_hit"] is False
        assert second["cache_hit"] is True
        assert first["commit"] == second["commit"] == revision
        assert first["tree"] == second["tree"]
        assert (root / "second" / "value.txt").read_text() == "frozen\n"
        assert not (root / "second" / "untracked.txt").exists()
        assert (
            (root / "first" / "value.txt").stat().st_ino
            != (root / "second" / "value.txt").stat().st_ino
        )
        assert first["populate_attempts"] == 1
        assert second["populate_attempts"] == 0


def test_exact_revision_cache_retries_population_from_a_clean_temporary_repo() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        remote, revision = _make_repository(root)
        cache = ExactRevisionSourceCache(root / "cache", timeout=10)
        populate = cache._populate
        attempt = 0

        def flaky_populate(*args: object, **kwargs: object) -> dict[str, object]:
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise RuntimeError("transient TLS fetch failure")
            return populate(*args, **kwargs)  # type: ignore[arg-type]

        with (
            mock.patch.object(cache, "_populate", side_effect=flaky_populate),
            mock.patch("envsolve_harness.execution.source_cache.time.sleep") as sleep,
        ):
            result = cache.acquire(
                repository="owner/repository",
                revision=revision,
                destination=root / "checkout",
                remote_url=str(remote),
            )

        assert result["cache_hit"] is False
        assert result["populate_attempts"] == 3
        assert sleep.call_args_list[:2] == [mock.call(1), mock.call(2)]
        assert not list((root / "cache").rglob("*.tmp-*"))
