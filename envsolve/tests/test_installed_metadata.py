from __future__ import annotations

from dataclasses import dataclass
import unittest

from envsolve.verification.installed_metadata import (
    collect_distribution_snapshot,
    installed_metadata_source,
)


@dataclass(frozen=True)
class FakeEntryPoint:
    name: str
    value: str
    group: str


class FakeDistribution:
    version = "2.0"
    metadata = {"Name": "sample-dist"}
    entry_points = (
        FakeEntryPoint("sample", "sample.cli:main", "console_scripts"),
        FakeEntryPoint("plugin", "sample.plugin:load", "sample.plugins"),
    )

    def __init__(self, files: dict[str, str | None]) -> None:
        self.files = files

    def read_text(self, filename: str) -> str | None:
        return self.files.get(filename)


class InstalledMetadataTests(unittest.TestCase):
    def test_collects_only_explicit_top_level_and_console_metadata(self) -> None:
        installed = FakeDistribution(
            {
                "METADATA": "Name: sample-dist\nVersion: 2.0\n",
                "top_level.txt": "sample\n# ignored\nsample\n",
                "entry_points.txt": "[console_scripts]\nsample=sample.cli:main\n",
            }
        )

        snapshot = collect_distribution_snapshot("sample-dist", installed)

        self.assertEqual(snapshot.name, "sample-dist")
        self.assertEqual(snapshot.version, "2.0")
        self.assertEqual(snapshot.top_level_modules, ("sample",))
        self.assertEqual([(item.name, item.target) for item in snapshot.console_scripts], [("sample", "sample.cli:main")])
        self.assertEqual(len(snapshot.metadata_sha256), 64)
        self.assertEqual(
            snapshot.metadata_sha256,
            "b5b7e20b20f6d0c6f7c2765503eb53c817f4e4608a845027fdb18a6784ffeafd",
        )

    def test_missing_top_level_does_not_guess_distribution_name(self) -> None:
        installed = FakeDistribution(
            {"METADATA": "Name: sample-dist\n", "entry_points.txt": ""}
        )

        snapshot = collect_distribution_snapshot("sample-dist", installed)

        self.assertEqual(snapshot.top_level_modules, ())

    def test_snapshot_hash_covers_entry_point_and_top_level_files(self) -> None:
        common = {"METADATA": "Name: sample-dist\n", "entry_points.txt": ""}
        first = collect_distribution_snapshot(
            "sample-dist", FakeDistribution({**common, "top_level.txt": "sample\n"})
        )
        second = collect_distribution_snapshot(
            "sample-dist", FakeDistribution({**common, "top_level.txt": "other\n"})
        )

        self.assertNotEqual(first.metadata_sha256, second.metadata_sha256)

    def test_metadata_is_required(self) -> None:
        with self.assertRaises(ValueError):
            collect_distribution_snapshot("sample-dist", FakeDistribution({}))

    def test_legacy_pkg_info_is_content_addressed(self) -> None:
        first_distribution = FakeDistribution(
            {"PKG-INFO": "Name: sample-dist\nVersion: 2.0\n", "top_level.txt": "sample\n"}
        )
        second_distribution = FakeDistribution(
            {"PKG-INFO": "Name: sample-dist\nVersion: 2.1\n", "top_level.txt": "sample\n"}
        )

        first = collect_distribution_snapshot("sample-dist", first_distribution)
        second = collect_distribution_snapshot("sample-dist", second_distribution)

        self.assertEqual(installed_metadata_source(first_distribution), "PKG-INFO")
        self.assertNotEqual(first.metadata_sha256, second.metadata_sha256)
        self.assertEqual(first.top_level_modules, ("sample",))

    def test_modern_metadata_is_preferred_over_pkg_info(self) -> None:
        distribution = FakeDistribution(
            {
                "METADATA": "Name: sample-dist\nVersion: 2.0\n",
                "PKG-INFO": "Name: sample-dist\nVersion: 1.0\n",
            }
        )

        snapshot = collect_distribution_snapshot("sample-dist", distribution)

        self.assertEqual(installed_metadata_source(distribution), "METADATA")
        self.assertEqual(len(snapshot.metadata_sha256), 64)


if __name__ == "__main__":
    unittest.main()
