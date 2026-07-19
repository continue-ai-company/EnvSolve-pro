from __future__ import annotations

import configparser
from dataclasses import dataclass
from enum import Enum
import hashlib
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python < 3.11
    import tomli as tomllib


class NativeProbeKind(str, Enum):
    PYTEST_COLLECTION = "pytest_collection"
    WHEEL_BUILD = "wheel_build"


@dataclass(frozen=True)
class NativeConfigEvidence:
    path: str
    sha256: str
    role: str


@dataclass(frozen=True)
class NativeProbe:
    probe_id: str
    kind: NativeProbeKind
    argv: tuple[str, ...]
    config_evidence: tuple[NativeConfigEvidence, ...]


@dataclass(frozen=True)
class NativePlan:
    probe: NativeProbe | None
    reason: str


@dataclass(frozen=True)
class NativeOutcome:
    exit_code: int | None
    timed_out: bool
    output_artifacts: tuple[str, ...] = ()


@dataclass(frozen=True)
class NativeDecision:
    passed: bool | None
    reason: str


class NativeProjectPlanner:
    def plan(
        self,
        project_root: Path,
        python_executable: str,
        wheel_directory: Path,
    ) -> NativePlan:
        root = project_root.resolve()
        pytest_evidence = self._pytest_evidence(root)
        if pytest_evidence:
            return NativePlan(
                NativeProbe(
                    probe_id="native:pytest-collection",
                    kind=NativeProbeKind.PYTEST_COLLECTION,
                    argv=(
                        python_executable,
                        "-m",
                        "pytest",
                        "--collect-only",
                        "-q",
                        "-p",
                        "no:cacheprovider",
                    ),
                    config_evidence=pytest_evidence,
                ),
                "project declares pytest configuration",
            )

        build_evidence = tuple(
            evidence
            for name, role in (
                ("pyproject.toml", "build-metadata"),
                ("setup.py", "legacy-build-script"),
            )
            if (evidence := self._file_evidence(root, name, role)) is not None
        )
        if build_evidence:
            return NativePlan(
                NativeProbe(
                    probe_id="native:wheel-build",
                    kind=NativeProbeKind.WHEEL_BUILD,
                    argv=(
                        python_executable,
                        "-m",
                        "pip",
                        "wheel",
                        "--no-deps",
                        "--no-build-isolation",
                        "--wheel-dir",
                        str(wheel_directory),
                        ".",
                    ),
                    config_evidence=build_evidence,
                ),
                "project declares Python build metadata",
            )
        return NativePlan(None, "no supported project-declared test or build entry point")

    def _pytest_evidence(self, root: Path) -> tuple[NativeConfigEvidence, ...]:
        pytest_ini = self._file_evidence(root, "pytest.ini", "pytest-config")
        if pytest_ini is not None:
            return (pytest_ini,)

        pyproject = root / "pyproject.toml"
        if pyproject.is_file():
            try:
                value = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, tomllib.TOMLDecodeError):
                value = {}
            tool = value.get("tool")
            pytest_table = tool.get("pytest") if isinstance(tool, dict) else None
            pytest_config = (
                pytest_table.get("ini_options")
                if isinstance(pytest_table, dict)
                else None
            )
            if isinstance(pytest_config, dict):
                evidence = self._file_evidence(
                    root, "pyproject.toml", "pytest-config"
                )
                return (evidence,) if evidence is not None else ()

        setup_cfg = root / "setup.cfg"
        if setup_cfg.is_file():
            parser = configparser.ConfigParser(interpolation=None)
            try:
                parser.read(setup_cfg, encoding="utf-8")
            except (configparser.Error, OSError, UnicodeError):
                pass
            else:
                if parser.has_section("tool:pytest"):
                    evidence = self._file_evidence(
                        root, "setup.cfg", "pytest-config"
                    )
                    return (evidence,) if evidence is not None else ()
        return ()

    @staticmethod
    def _file_evidence(
        root: Path, name: str, role: str
    ) -> NativeConfigEvidence | None:
        path = root / name
        if not path.is_file():
            return None
        try:
            payload = path.read_bytes()
        except OSError:
            return None
        return NativeConfigEvidence(
            path=name,
            sha256=hashlib.sha256(payload).hexdigest(),
            role=role,
        )


def evaluate_native_outcome(
    plan: NativePlan,
    outcome: NativeOutcome | None,
) -> NativeDecision:
    if plan.probe is None:
        return NativeDecision(None, plan.reason)
    if outcome is None:
        return NativeDecision(None, "native probe outcome missing")
    if outcome.timed_out:
        return NativeDecision(False, "native probe timed out")
    if outcome.exit_code is None:
        return NativeDecision(None, "native probe exit code missing")
    if outcome.exit_code != 0:
        if (
            plan.probe.kind == NativeProbeKind.PYTEST_COLLECTION
            and outcome.exit_code == 5
        ):
            return NativeDecision(None, "pytest reported no collectable tests")
        return NativeDecision(False, "native probe exited nonzero")
    if (
        plan.probe.kind == NativeProbeKind.WHEEL_BUILD
        and not outcome.output_artifacts
    ):
        return NativeDecision(False, "wheel build produced no wheel artifact")
    return NativeDecision(True, "project-native collection or build passed")
