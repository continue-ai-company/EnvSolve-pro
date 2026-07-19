from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from envsolve.tools.run_p5_v3_in_container import (
    aggregate_decisions,
    canonical_distribution_name,
    default_route_present,
    direct_url_project_path,
    find_project_distributions,
    is_project_distribution,
    legacy_egg_link_target,
)
from envsolve.tools.run_p5_v3_dev5 import (
    clean_checkout,
    merge_preregistration,
    pre_bootstrap_directory_script,
    run,
    validate_verifier_inputs,
    verifier_invocation,
)
from envsolve.verification.smoke import SmokeDecision


class V3ContainerToolTests(unittest.TestCase):
    def test_accepts_only_local_project_direct_urls(self) -> None:
        root = Path("/data/project")

        self.assertTrue(is_project_distribution('{"url":"file:///data/project"}', root))
        self.assertTrue(is_project_distribution('{"url":"file:///data/project/pkg"}', root))
        self.assertFalse(is_project_distribution('{"url":"file:///other"}', root))
        self.assertFalse(is_project_distribution('{"url":"https://example.com/pkg"}', root))
        self.assertFalse(is_project_distribution("not json", root))

    def test_decodes_file_url(self) -> None:
        self.assertEqual(
            direct_url_project_path('{"url":"file:///data/a%20b"}'), Path("/data/a b")
        )

    def test_legacy_editable_requires_link_and_project_metadata_name_match(self) -> None:
        class FakeDistribution:
            def __init__(self, name: str, version: str = "1.0") -> None:
                self.metadata = {"Name": name}
                self.version = version

            def read_text(self, filename: str) -> str | None:
                return None

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            site_packages = Path(directory) / "site-packages"
            root.mkdir()
            site_packages.mkdir()
            link = site_packages / "Sample_Dist.egg-link"
            link.write_text(f"{root}\n.\n", encoding="utf-8")

            matches = find_project_distributions(
                root,
                installed_distributions=(),
                project_owned_distributions=(FakeDistribution("sample-dist"),),
                egg_links=(link,),
            )

            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].provenance_kind, "legacy-egg-link")
            self.assertEqual(len(matches[0].provenance_sha256), 64)

    def test_legacy_editable_rejects_outside_mismatch_and_ambiguity(self) -> None:
        class FakeDistribution:
            version = "1.0"

            def __init__(self, name: str) -> None:
                self.metadata = {"Name": name}

            def read_text(self, filename: str) -> str | None:
                return None

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            link = Path(directory) / "sample.egg-link"
            link.write_text("/outside/project\n", encoding="utf-8")
            self.assertEqual(
                find_project_distributions(
                    root,
                    installed_distributions=(),
                    project_owned_distributions=(FakeDistribution("sample"),),
                    egg_links=(link,),
                ),
                (),
            )
            link.write_text(f"{root}\n", encoding="utf-8")
            self.assertEqual(
                find_project_distributions(
                    root,
                    installed_distributions=(),
                    project_owned_distributions=(FakeDistribution("other"),),
                    egg_links=(link,),
                ),
                (),
            )
            self.assertEqual(
                find_project_distributions(
                    root,
                    installed_distributions=(),
                    project_owned_distributions=(
                        FakeDistribution("sample"),
                        FakeDistribution("sample"),
                    ),
                    egg_links=(link,),
                ),
                (),
            )

    def test_legacy_path_and_canonical_name_parsers_fail_closed(self) -> None:
        self.assertEqual(canonical_distribution_name("Sample_Dist.name"), "sample-dist-name")
        self.assertIsNone(legacy_egg_link_target("relative/path\n"))

    def test_default_route_parser_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            route = Path(directory) / "route"
            route.write_text(
                "Iface Destination Gateway Flags RefCnt Use Metric Mask\n"
                "eth0 00000000 010011AC 0003 0 0 0 00000000\n",
                encoding="utf-8",
            )
            self.assertTrue(default_route_present(route))
            route.write_text(
                "Iface Destination Gateway Flags RefCnt Use Metric Mask\n",
                encoding="utf-8",
            )
            self.assertFalse(default_route_present(route))
            self.assertTrue(default_route_present(route.with_name("missing")))

    def test_aggregate_decision_is_three_valued(self) -> None:
        passed = SmokeDecision(True, "ok", ("a",))
        failed = SmokeDecision(False, "bad", ("b",))
        unknown = SmokeDecision(None, "unknown", ())

        self.assertTrue(aggregate_decisions((passed, passed)).passed)
        self.assertFalse(aggregate_decisions((passed, failed)).passed)
        self.assertIsNone(aggregate_decisions((passed, unknown)).passed)
        self.assertIsNone(aggregate_decisions(()).passed)
        self.assertIsNone(
            aggregate_decisions((passed,), collection_error_count=1).passed
        )
        self.assertFalse(
            aggregate_decisions(
                (passed, failed), collection_error_count=1
            ).passed
        )

    def test_preregistration_inheritance_rejects_overrides(self) -> None:
        base = {"environment": {"image": "frozen"}, "targets": ["one"]}
        overlay = {
            "preregistration_id": "next",
            "base_preregistration": {"inherit": ["environment", "targets"]},
        }

        merged = merge_preregistration(base, overlay)

        self.assertEqual(merged["environment"], base["environment"])
        self.assertEqual(merged["targets"], base["targets"])
        with self.assertRaises(ValueError):
            merge_preregistration(base, {**overlay, "targets": []})

    def test_pre_bootstrap_directories_are_declared_and_fail_on_collision(self) -> None:
        script = pre_bootstrap_directory_script(
            {"runner_contract": {"pre_bootstrap_directories": ["build_output"]}}
        )

        self.assertIn("test ! -e build_output", script)
        self.assertIn("mkdir -- build_output", script)
        self.assertNotIn("results.json", script)
        with self.assertRaises(ValueError):
            pre_bootstrap_directory_script(
                {"runner_contract": {"pre_bootstrap_directories": ["../source"]}}
            )
        for invalid in ("build_output", ["build_output", 1], ["."], [["nested"]]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                pre_bootstrap_directory_script(
                    {"runner_contract": {"pre_bootstrap_directories": invalid}}
                )

    def test_v1_extras_are_bound_to_frozen_bootstrap_hashes(self) -> None:
        first = {"bootstrap": {"sha256": "a" * 64}}
        second = {"bootstrap": {"sha256": "b" * 64}}
        prereg = {
            "verification_level": "V1",
            "targets": [first, second],
            "environment_plan": {
                "selected_extras_by_bootstrap_sha256": {
                    "a" * 64: ["test"],
                    "b" * 64: [],
                }
            },
        }

        validate_verifier_inputs(prereg)
        level, path, arguments = verifier_invocation(prereg, first)

        self.assertEqual(level, "V1")
        self.assertEqual(path, "envsolve/tools/run_p5_v1_in_container.py")
        self.assertEqual(arguments, ("--selected-extra", "test"))

    def test_v1_extras_fail_closed_on_missing_or_unsafe_input(self) -> None:
        target = {"bootstrap": {"sha256": "a" * 64}}
        base = {
            "verification_level": "V1",
            "targets": [target],
            "environment_plan": {"selected_extras_by_bootstrap_sha256": {}},
        }

        with self.assertRaises(ValueError):
            validate_verifier_inputs(base)
        with self.assertRaises(ValueError):
            verifier_invocation(
                {
                    **base,
                    "environment_plan": {
                        "selected_extras_by_bootstrap_sha256": {
                            "a" * 64: ["test; touch /tmp/unsafe"]
                        }
                    },
                },
                target,
            )

    def test_v4_uses_only_the_fixed_native_collector(self) -> None:
        level, path, arguments = verifier_invocation(
            {"verification_level": "V4"}, {"bootstrap": {"sha256": "a" * 64}}
        )

        self.assertEqual(level, "V4")
        self.assertEqual(path, "envsolve/tools/run_p5_v4_in_container.py")
        self.assertEqual(arguments, ())

        with self.assertRaises(ValueError):
            verifier_invocation(
                {"verification_level": "custom-command"},
                {"bootstrap": {"sha256": "a" * 64}},
            )

    def test_v6_uses_only_the_fixed_snapshot_collector(self) -> None:
        level, path, arguments = verifier_invocation(
            {"verification_level": "V6"}, {"bootstrap": {"sha256": "a" * 64}}
        )

        self.assertEqual(level, "V6")
        self.assertEqual(path, "envsolve/tools/run_p5_v6_in_container.py")
        self.assertEqual(arguments, ())

    def test_clean_checkout_ignores_dirty_retained_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            destination = Path(directory) / "destination"
            source.mkdir()
            self.assertEqual(run(["git", "init", str(source)]).returncode, 0)
            self.assertEqual(
                run(["git", "-C", str(source), "config", "user.email", "test@example.com"]).returncode,
                0,
            )
            self.assertEqual(
                run(["git", "-C", str(source), "config", "user.name", "Test"]).returncode,
                0,
            )
            tracked = source / "value.txt"
            tracked.write_text("committed\n", encoding="utf-8")
            self.assertEqual(run(["git", "-C", str(source), "add", "value.txt"]).returncode, 0)
            self.assertEqual(run(["git", "-C", str(source), "commit", "-m", "initial"]).returncode, 0)
            revision = run(["git", "-C", str(source), "rev-parse", "HEAD"]).stdout.strip()
            tracked.write_text("dirty\n", encoding="utf-8")

            provenance = clean_checkout(source, revision, destination)

            self.assertEqual(provenance["head"], revision)
            self.assertEqual(provenance["source_materialization"], "detached_git_checkout")
            self.assertTrue((destination / ".git").is_dir())
            self.assertEqual((destination / "value.txt").read_text(encoding="utf-8"), "committed\n")
            self.assertEqual(
                run(["git", "-C", str(destination), "status", "--porcelain"]).stdout,
                "",
            )


if __name__ == "__main__":
    unittest.main()
