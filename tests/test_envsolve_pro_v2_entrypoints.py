from __future__ import annotations

import unittest

from envsolve_harness.runners.envsolve_pro_v2_registry import (
    register_envsolve_pro_v2_runners,
)
from envsolve_harness.runners.registry import registered_solver_runners
from experiments.run_envsolve_pro_v2_schedule import (
    _provider_execution_metadata,
    _validate_provider_environment,
)


class EnvSolveProV2EntrypointTest(unittest.TestCase):
    def test_v2_runners_are_registered_outside_the_frozen_registry(self) -> None:
        register_envsolve_pro_v2_runners()

        registered = set(registered_solver_runners())
        self.assertIn("deepseek-repository-agent", registered)
        self.assertIn("deepseek-goal-aware-agent", registered)
        self.assertIn("deepseek-free-agent", registered)
        self.assertIn("envsolve-pro-v2-atomic", registered)
        self.assertIn("envsolve-pro-v2-atomic-handoff", registered)
        self.assertIn("envsolve-pro-v2", registered)
        self.assertIn("envsolve-pro-v2-incumbent", registered)
        self.assertIn("envsolve-pro-v2-ledger", registered)
        self.assertIn("envsolve-pro-v2-scheduled-observation", registered)
        self.assertIn("envsolve-pro-v2-verifier-handoff", registered)
        self.assertIn("envsolve-pro-v2-stateful-replay", registered)

    def test_openrouter_preflight_requires_only_the_openrouter_key(self) -> None:
        identities = [
            {"runner": "envsolve-pro-v2-atomic"},
            {"runner": "envsolve-pro-v2-atomic-handoff"},
            {"runner": "envsolve-pro-v2"},
            {"runner": "envsolve-pro-v2-verifier-handoff"},
            {"runner": "envsolve-pro-v2-stateful-replay"},
        ]
        with self.assertRaisesRegex(RuntimeError, "OPENROUTER_API_KEY"):
            _validate_provider_environment(identities, {})

        _validate_provider_environment(
            identities,
            {"OPENROUTER_API_KEY": "present-not-recorded"},
        )

    def test_provider_metadata_records_route_but_not_key(self) -> None:
        metadata = _provider_execution_metadata(
            [{"runner": "deepseek-free-agent"}],
            {
                "OPENROUTER_API_KEY": "must-not-be-recorded",
                "OPENROUTER_PROVIDER_ORDER": "cloudflare",
            },
        )

        self.assertEqual(
            metadata,
            {
                "provider_backed": True,
                "credential_variable": "OPENROUTER_API_KEY",
                "base_url": "https://openrouter.ai/api/v1",
                "provider_order": ["cloudflare"],
            },
        )
        self.assertNotIn("must-not-be-recorded", repr(metadata))

    def test_deepseek_direct_preflight_and_metadata_use_direct_key(self) -> None:
        identities = [
            {
                "runner": "envsolve-pro-v2-stateful-replay",
                "model": "deepseek-v4-flash",
            }
        ]
        with self.assertRaisesRegex(RuntimeError, "DEEPSEEK_API_KEY"):
            _validate_provider_environment(identities, {})

        _validate_provider_environment(
            identities,
            {"DEEPSEEK_API_KEY": "present-not-recorded"},
        )
        self.assertEqual(
            _provider_execution_metadata(identities, {}),
            {
                "provider_backed": True,
                "provider": "deepseek-direct",
                "base_url": "https://api.deepseek.com",
                "credential_variable": "DEEPSEEK_API_KEY",
            },
        )


if __name__ == "__main__":
    unittest.main()
