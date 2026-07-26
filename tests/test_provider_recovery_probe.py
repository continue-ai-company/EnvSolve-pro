from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "probe_provider_recovery",
    ROOT / "experiments" / "probe_provider_recovery.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProviderRecoveryProbeTest(unittest.TestCase):
    def test_fault_injection_probe_qualifies_both_branches(self) -> None:
        result = MODULE.run_probe()

        self.assertTrue(result["result"]["qualified"])
        recovered = result["result"]["recovered"]["usage"]
        exhausted = result["result"]["exhausted"]
        self.assertEqual(recovered["response_parse_recoveries"], 1)
        self.assertEqual(
            [
                item["outcome"]
                for item in result["result"]["recovered"]["provider_attempts"]
            ],
            ["error", "response"],
        )
        self.assertEqual(exhausted["usage"]["response_parse_retries"], 2)
        self.assertEqual(
            [item["outcome"] for item in exhausted["provider_attempts"]],
            ["error", "error", "error"],
        )
        self.assertEqual(exhausted["terminal"]["attempts"], 3)


if __name__ == "__main__":
    unittest.main()
