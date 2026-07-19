from __future__ import annotations

import unittest

from envsolve.verification.smoke import (
    ConsoleEntryPoint,
    DistributionSnapshot,
    MetadataSmokePlanner,
    ProbeOutcome,
    SmokeProbe,
    SmokeProbeKind,
    decide_smoke,
    execute_smoke_plan,
)


HASH = "a" * 64


class MetadataSmokePlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = MetadataSmokePlanner()

    def snapshot(self, **changes: object) -> DistributionSnapshot:
        values = {
            "name": "sample-dist",
            "version": "1.2.3",
            "metadata_sha256": HASH,
            "top_level_modules": ("sample",),
            "console_scripts": (),
        }
        values.update(changes)
        return DistributionSnapshot(**values)  # type: ignore[arg-type]

    def test_package_probe_uses_isolated_python_and_argv(self) -> None:
        plan = self.planner.plan(self.snapshot())

        self.assertEqual(len(plan.probes), 1)
        self.assertEqual(plan.probes[0].kind, SmokeProbeKind.PACKAGE_IMPORT)
        self.assertEqual(plan.probes[0].argv[:3], ("python", "-I", "-c"))
        self.assertEqual(plan.probes[0].argv[-1], "sample")

    def test_distribution_name_is_not_guessed_as_import_name(self) -> None:
        plan = self.planner.plan(self.snapshot(top_level_modules=()))

        self.assertEqual(plan.probes, ())
        self.assertIsNone(decide_smoke(plan, ()).passed)

    def test_console_entry_gets_import_and_cli_coverage(self) -> None:
        plan = self.planner.plan(
            self.snapshot(
                console_scripts=(ConsoleEntryPoint("sample-cli", "sample.cli:main [fast]"),)
            )
        )

        kinds = [item.kind for item in plan.probes]
        self.assertEqual(
            kinds,
            [
                SmokeProbeKind.PACKAGE_IMPORT,
                SmokeProbeKind.ENTRY_POINT_IMPORT,
                SmokeProbeKind.CLI_RESOLUTION,
            ],
        )
        self.assertEqual(plan.probes[-1].argv[-1], "sample-cli")
        self.assertEqual(plan.probes[-1].argv[:3], ("python", "-I", "-c"))

    def test_unsafe_metadata_is_rejected_without_shell_interpolation(self) -> None:
        plan = self.planner.plan(
            self.snapshot(
                top_level_modules=("sample; touch /tmp/pwned",),
                console_scripts=(ConsoleEntryPoint("bad/tool", "sample.cli:main"),),
            )
        )

        self.assertEqual(plan.probes, ())
        self.assertEqual(len(plan.rejections), 2)
        self.assertIsNone(decide_smoke(plan, ()).passed)

    def test_invalid_or_ambiguous_entry_point_is_rejected(self) -> None:
        plan = self.planner.plan(
            self.snapshot(
                console_scripts=(
                    ConsoleEntryPoint("sample", "sample.cli:main"),
                    ConsoleEntryPoint("sample", "sample.other:main"),
                )
            )
        )

        self.assertTrue(plan.rejections)
        self.assertIsNone(decide_smoke(plan, ()).passed)

    def test_all_planned_zero_exit_outcomes_pass(self) -> None:
        plan = self.planner.plan(
            self.snapshot(console_scripts=(ConsoleEntryPoint("sample", "sample.cli:main"),))
        )
        outcomes = tuple(ProbeOutcome(item.probe_id, 0) for item in plan.probes)

        decision = decide_smoke(plan, outcomes)

        self.assertTrue(decision.passed)

    def test_missing_outcome_is_unknown(self) -> None:
        plan = self.planner.plan(
            self.snapshot(console_scripts=(ConsoleEntryPoint("sample", "sample.cli:main"),))
        )

        decision = decide_smoke(plan, (ProbeOutcome(plan.probes[0].probe_id, 0),))

        self.assertIsNone(decision.passed)

    def test_nonzero_or_timeout_fails(self) -> None:
        plan = self.planner.plan(self.snapshot())

        self.assertFalse(decide_smoke(plan, (ProbeOutcome(plan.probes[0].probe_id, 2),)).passed)
        self.assertFalse(
            decide_smoke(
                plan,
                (ProbeOutcome(plan.probes[0].probe_id, None, timed_out=True),),
            ).passed
        )

    def test_unknown_and_duplicate_outcomes_are_rejected(self) -> None:
        plan = self.planner.plan(self.snapshot())
        outcome = ProbeOutcome(plan.probes[0].probe_id, 0)

        with self.assertRaises(ValueError):
            decide_smoke(plan, (outcome, outcome))
        with self.assertRaises(ValueError):
            decide_smoke(plan, (ProbeOutcome("unplanned", 0),))

    def test_executor_requires_isolated_runner_contract(self) -> None:
        class RecordingRunner:
            calls: list[tuple[SmokeProbe, int, bool, bool]] = []

            def run(
                self,
                probe: SmokeProbe,
                *,
                timeout_seconds: int,
                network_disabled: bool,
                empty_workdir: bool,
            ) -> ProbeOutcome:
                self.calls.append(
                    (probe, timeout_seconds, network_disabled, empty_workdir)
                )
                return ProbeOutcome(probe.probe_id, 0)

        plan = self.planner.plan(self.snapshot())
        runner = RecordingRunner()

        _, decision = execute_smoke_plan(plan, runner)

        self.assertTrue(decision.passed)
        self.assertEqual(runner.calls[0][1:], (30, True, True))


if __name__ == "__main__":
    unittest.main()
