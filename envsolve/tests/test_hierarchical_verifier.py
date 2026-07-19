from __future__ import annotations

import unittest

from envsolve.verification.hierarchy import VerificationLevel, build_report


def level(identifier: str, passed: bool | None, applicable: bool = True) -> VerificationLevel:
    return VerificationLevel(identifier, passed, f"verifier-{identifier}", "synthetic", applicable)


class HierarchicalVerifierTests(unittest.TestCase):
    def test_official_pass_does_not_imply_robust_pass(self) -> None:
        report = build_report((level("V0", True), level("V2", True)))
        self.assertTrue(report.official_pass)
        self.assertFalse(report.robust_pass)

    def test_robust_pass_requires_all_explicit_levels(self) -> None:
        report = build_report(
            tuple(level(identifier, True) for identifier in ("V0", "V1", "V2", "V3", "V4", "V6"))
        )
        self.assertTrue(report.official_pass)
        self.assertTrue(report.robust_pass)
        self.assertIsNone(report.native_pass)

    def test_unknown_level_fails_closed(self) -> None:
        report = build_report(
            (
                level("V0", True),
                level("V1", True),
                level("V2", True),
                level("V3", None),
                level("V4", True),
                level("V6", True),
            )
        )
        self.assertFalse(report.robust_pass)

    def test_native_pass_requires_applicable_v5(self) -> None:
        levels = [level(identifier, True) for identifier in ("V0", "V1", "V2", "V3", "V4", "V6")]
        levels.append(level("V5", False))
        self.assertFalse(build_report(tuple(levels)).native_pass)

    def test_duplicate_level_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_report((level("V0", True), level("V0", False)))
