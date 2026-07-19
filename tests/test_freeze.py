from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from envsolve_harness.integrity.freeze import _git_worktree_map, _verify_file_map
from envsolve_harness.utils.provenance import sha256_file


class FreezeFileMapTest(unittest.TestCase):
    def test_detects_missing_and_modified_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            present = root / "present.txt"
            present.write_text("original\n", encoding="utf-8")
            expected = {
                "present.txt": sha256_file(present),
                "missing.txt": "0" * 64,
            }
            present.write_text("modified\n", encoding="utf-8")

            errors = _verify_file_map(root, expected, "fixture")
            self.assertEqual(
                errors,
                [
                    "fixture: hash mismatch for present.txt",
                    "fixture: missing file missing.txt",
                ],
            )

    def test_git_worktree_map_captures_deletions_files_and_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            tracked = root / "tracked.txt"
            tracked.write_text("tracked\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(root), "add", "tracked.txt"],
                check=True,
            )
            tracked.unlink()
            untracked = root / "untracked.txt"
            untracked.write_text("untracked\n", encoding="utf-8")
            (root / "link.txt").symlink_to("untracked.txt")

            self.assertEqual(
                _git_worktree_map(root),
                {
                    "link.txt": "symlink:untracked.txt",
                    "tracked.txt": "missing",
                    "untracked.txt": f"sha256:{sha256_file(untracked)}",
                },
            )


if __name__ == "__main__":
    unittest.main()
