from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from envsolve.runtime.verifier import _IMPORT_PROBE, _PROBE_MARKER
from envsolve.verification.imports import (
    EnvironmentFacts,
    ImportContextAnalyzer,
    MissingImportFinding,
)
from envsolve.verification.obligations import (
    ObligationDisposition,
    ObligationLayer,
    ResolutionStatus,
    decide_import_obligation,
)


FACTS = EnvironmentFacts(sys_platform="linux", python_major=3, platform_name="Linux")


class TwoLayerImportObligationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = ImportContextAnalyzer()

    def decide(
        self,
        source: str,
        line: int,
        runtime: ResolutionStatus,
        static: ResolutionStatus,
        *,
        module: str = "dependency",
        fallback_modules: tuple[str, ...] = (),
        runtime_statuses: dict[str, ResolutionStatus] | None = None,
    ):
        assessment = self.analyzer.assess(
            MissingImportFinding(module, "src/app.py", line, "unresolved"),
            source,
            FACTS,
        )
        return decide_import_obligation(
            assessment,
            runtime,
            static,
            fallback_modules=fallback_modules,
            runtime_statuses=runtime_statuses or {},
        )

    def test_s1_active_import_missing_in_both_layers(self) -> None:
        decision = self.decide(
            "import dependency\n",
            0,
            ResolutionStatus.MISSING,
            ResolutionStatus.MISSING,
        )
        self.assertEqual(decision.disposition, ObligationDisposition.ACTIVE)
        self.assertEqual(
            decision.active_layers,
            (
                ObligationLayer.RUNTIME_SEMANTIC,
                ObligationLayer.STATIC_SOURCE,
            ),
        )

    def test_s2_active_import_resolved_in_both_layers(self) -> None:
        decision = self.decide(
            "import dependency\n",
            0,
            ResolutionStatus.RESOLVED,
            ResolutionStatus.RESOLVED,
        )
        self.assertEqual(decision.disposition, ObligationDisposition.INACTIVE)

    def test_s3_guarded_optional_is_still_static_obligation(self) -> None:
        source = (
            "try:\n"
            "    import dependency\n"
            "except ImportError:\n"
            "    dependency = None\n"
        )
        decision = self.decide(
            source, 1, ResolutionStatus.MISSING, ResolutionStatus.MISSING
        )
        self.assertEqual(decision.disposition, ObligationDisposition.ACTIVE)
        self.assertEqual(decision.active_layers, (ObligationLayer.STATIC_SOURCE,))

    def test_s4_resolved_primary_does_not_waive_static_fallback(self) -> None:
        source = (
            "try:\n"
            "    import primary\n"
            "except ImportError:\n"
            "    import dependency\n"
        )
        decision = self.decide(
            source,
            3,
            ResolutionStatus.MISSING,
            ResolutionStatus.MISSING,
            fallback_modules=("primary",),
            runtime_statuses={"primary": ResolutionStatus.RESOLVED},
        )
        self.assertEqual(decision.disposition, ObligationDisposition.ACTIVE)
        self.assertEqual(decision.active_layers, (ObligationLayer.STATIC_SOURCE,))

    def test_s5_dynamic_runtime_alias_does_not_satisfy_static_layer(self) -> None:
        decision = self.decide(
            "import dependency\n",
            0,
            ResolutionStatus.RESOLVED,
            ResolutionStatus.MISSING,
        )
        self.assertEqual(decision.disposition, ObligationDisposition.ACTIVE)
        self.assertEqual(decision.active_layers, (ObligationLayer.STATIC_SOURCE,))

    def test_s6_type_checking_stub_satisfies_static_only_import(self) -> None:
        source = (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    import dependency\n"
        )
        decision = self.decide(
            source, 2, ResolutionStatus.MISSING, ResolutionStatus.RESOLVED
        )
        self.assertEqual(decision.disposition, ObligationDisposition.INACTIVE)
        self.assertEqual(
            decision.required_layers, (ObligationLayer.STATIC_SOURCE,)
        )

    def test_s7_missing_type_checking_import_is_static_failure(self) -> None:
        source = (
            "import typing\n"
            "if typing.TYPE_CHECKING:\n"
            "    import dependency\n"
        )
        decision = self.decide(
            source, 2, ResolutionStatus.MISSING, ResolutionStatus.MISSING
        )
        self.assertEqual(decision.disposition, ObligationDisposition.ACTIVE)
        self.assertEqual(decision.active_layers, (ObligationLayer.STATIC_SOURCE,))

    def test_s8_inactive_platform_branch_waives_both_layers(self) -> None:
        source = 'import sys\nif sys.platform == "darwin":\n    import dependency\n'
        decision = self.decide(
            source, 2, ResolutionStatus.MISSING, ResolutionStatus.MISSING
        )
        self.assertEqual(decision.disposition, ObligationDisposition.INACTIVE)
        self.assertFalse(decision.required_layers)

    def test_s9_runtime_execution_error_remains_unknown(self) -> None:
        decision = self.decide(
            "import dependency\n",
            0,
            ResolutionStatus.UNKNOWN,
            ResolutionStatus.RESOLVED,
        )
        self.assertEqual(decision.disposition, ObligationDisposition.UNKNOWN)
        self.assertEqual(
            decision.unknown_layers, (ObligationLayer.RUNTIME_SEMANTIC,)
        )

    def test_s10_unsupported_static_layout_remains_unknown(self) -> None:
        decision = self.decide(
            "import dependency\n",
            0,
            ResolutionStatus.UNKNOWN,
            ResolutionStatus.UNKNOWN,
        )
        self.assertEqual(decision.disposition, ObligationDisposition.UNKNOWN)
        self.assertEqual(
            decision.unknown_layers,
            (
                ObligationLayer.RUNTIME_SEMANTIC,
                ObligationLayer.STATIC_SOURCE,
            ),
        )

    def test_runtime_only_ablation_ignores_only_static_layer(self) -> None:
        decision = self.decide(
            "import dependency\n",
            0,
            ResolutionStatus.RESOLVED,
            ResolutionStatus.MISSING,
        )
        assessment = self.analyzer.assess(
            MissingImportFinding("dependency", "src/app.py", 0, "unresolved"),
            "import dependency\n",
            FACTS,
        )
        ablated = decide_import_obligation(
            assessment,
            ResolutionStatus.RESOLVED,
            ResolutionStatus.MISSING,
            static_layer_enabled=False,
        )

        self.assertEqual(decision.disposition, ObligationDisposition.ACTIVE)
        self.assertEqual(ablated.disposition, ObligationDisposition.INACTIVE)
        self.assertEqual(
            ablated.required_layers, (ObligationLayer.RUNTIME_SEMANTIC,)
        )

    def test_probe_distinguishes_physical_alias_and_stub_layouts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "physical_dependency.py").write_text("VALUE = 1\n", encoding="utf-8")
            mapped_path = root / "editable" / "mapped_dependency.py"
            mapped_path.parent.mkdir()
            mapped_path.write_text("VALUE = 3\n", encoding="utf-8")
            alias = root / "alias_package"
            alias.mkdir()
            backend = root / "actual_backend.py"
            backend.write_text("VALUE = 2\n", encoding="utf-8")
            (alias / "__init__.py").write_text(
                "import importlib.machinery\n"
                "import sys\n"
                "import types\n"
                "child = types.ModuleType(__name__ + '.child')\n"
                "child.__spec__ = importlib.machinery.ModuleSpec(\n"
                f"    __name__ + '.child', loader=None, origin={str(backend)!r}\n"
                ")\n"
                "sys.modules[__name__ + '.child'] = child\n",
                encoding="utf-8",
            )
            stubs = root / "typed_dependency-stubs"
            stubs.mkdir()
            (stubs / "__init__.pyi").write_text("VALUE: int\n", encoding="utf-8")
            modules = [
                "physical_dependency",
                "alias_package.child",
                "typed_dependency",
                "absent_dependency",
                "mapped_dependency",
            ]
            code = (
                "import importlib.machinery\n"
                "import sys\n"
                "import types\n"
                f"sys.path.insert(0, {str(root)!r})\n"
                "mapped = types.ModuleType('mapped_dependency')\n"
                "mapped.__spec__ = importlib.machinery.ModuleSpec(\n"
                f"    'mapped_dependency', loader=None, origin={str(mapped_path)!r}\n"
                ")\n"
                "sys.modules['mapped_dependency'] = mapped\n"
                + _IMPORT_PROBE
            )

            result = subprocess.run(
                [sys.executable, "-c", code, json.dumps(modules)],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            marker = next(
                line for line in result.stdout.splitlines() if line.startswith(_PROBE_MARKER)
            )
            payload = json.loads(marker[len(_PROBE_MARKER) :])
            self.assertEqual(
                payload["static"]["physical_dependency"]["status"], "resolved"
            )
            self.assertEqual(
                payload["runtime"]["alias_package.child"]["status"], "resolved"
            )
            self.assertEqual(
                payload["static"]["alias_package.child"]["status"], "missing"
            )
            self.assertEqual(
                payload["runtime"]["typed_dependency"]["status"], "missing"
            )
            self.assertEqual(
                payload["static"]["typed_dependency"]["status"], "resolved"
            )
            self.assertEqual(
                payload["static"]["absent_dependency"]["status"], "missing"
            )
            self.assertEqual(
                payload["static"]["mapped_dependency"]["kind"],
                "mapped_physical_origin",
            )
