from __future__ import annotations

import unittest

from envsolve_harness.calibration_analysis import classify_calibration_outcome


class CalibrationOutcomeTest(unittest.TestCase):
    def test_classifies_internal_false_calibration_outcomes(self) -> None:
        self.assertEqual(
            classify_calibration_outcome(False, True, True),
            "internal_false_official_true",
        )
        self.assertEqual(
            classify_calibration_outcome(False, True, False),
            "internal_false_official_false",
        )
        self.assertEqual(
            classify_calibration_outcome(False, False, False),
            "official_unknown",
        )

    def test_does_not_treat_incomplete_result_as_boolean(self) -> None:
        self.assertEqual(
            classify_calibration_outcome(True, False, True),
            "official_unknown",
        )


if __name__ == "__main__":
    unittest.main()
