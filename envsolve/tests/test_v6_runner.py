from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import unittest

from envsolve.tools.run_p5_v6_dev5 import collect_observation
from envsolve.verification.replay_equivalence import (
    ReplayIdentity,
    build_snapshot,
)


class V6RunnerTests(unittest.TestCase):
    def test_direct_script_entrypoint_loads_workspace_package(self) -> None:
        root = Path(__file__).resolve().parents[2]
        process = subprocess.run(
            [sys.executable, str(root / "envsolve/tools/run_p5_v6_dev5.py"), "--help"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("paired fresh-container P5 V6 replay", process.stdout)

    def identity(self) -> ReplayIdentity:
        return ReplayIdentity(
            image_id="image",
            repository_digest="digest",
            platform="linux/arm64",
            repository="org/repo",
            revision="revision",
            git_tree="tree",
            bootstrap_sha256="a" * 64,
            preregistration_sha256="b" * 64,
        )

    def replay(self):
        snapshot = build_snapshot(
            {"implementation": "CPython", "version": "3.13"},
            {"sys_platform": "linux"},
            (("dep", "1"),),
            (("sample", "1", "c" * 64, "pep610-direct-url", "d" * 64),),
        )
        return {
            "source": {
                "head": "revision",
                "git_tree": "tree",
                "pre_bootstrap_status_sha256": hashlib.sha256(b"").hexdigest(),
            },
            "container": {"networks_after_disconnect": []},
            "v6": {
                "network": {
                    "host_disconnect_marker": True,
                    "default_route_present": False,
                },
                "collection_errors": [],
                "snapshot": {
                    "sha256": snapshot.sha256,
                    "python_runtime": dict(snapshot.python_runtime),
                    "marker_environment": dict(snapshot.marker_environment),
                    "installed_distributions": [
                        item.__dict__ for item in snapshot.installed_distributions
                    ],
                    "project_distributions": [
                        item.__dict__ for item in snapshot.project_distributions
                    ],
                },
            },
        }

    def test_accepts_complete_clean_network_isolated_snapshot(self) -> None:
        observation, errors = collect_observation(self.identity(), self.replay())

        self.assertIsNotNone(observation.snapshot)
        self.assertEqual(errors, ())

    def test_network_or_source_mismatch_invalidates_snapshot(self) -> None:
        network = self.replay()
        network["container"]["networks_after_disconnect"] = ["bridge"]
        source = self.replay()
        source["source"]["git_tree"] = "other"

        for replay in (network, source):
            with self.subTest(replay=replay):
                observation, errors = collect_observation(self.identity(), replay)
                self.assertIsNone(observation.snapshot)
                self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
