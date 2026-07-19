from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import keyword
import re
from typing import Iterable, Protocol


_HASH = re.compile(r"^[0-9a-f]{64}$")
_EXECUTABLE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
_IMPORT_CODE = "import importlib,sys; importlib.import_module(sys.argv[1])"
_CLI_RESOLUTION_CODE = (
    "import shutil,sys; raise SystemExit(0 if shutil.which(sys.argv[1]) else 1)"
)
_ENTRY_POINT_CODE = (
    "import importlib,sys\n"
    "value = importlib.import_module(sys.argv[1])\n"
    "for part in sys.argv[2].split('.'):\n"
    "    value = getattr(value, part)\n"
)


class SmokeProbeKind(str, Enum):
    PACKAGE_IMPORT = "package_import"
    ENTRY_POINT_IMPORT = "entry_point_import"
    CLI_RESOLUTION = "cli_resolution"


@dataclass(frozen=True)
class ConsoleEntryPoint:
    name: str
    target: str


@dataclass(frozen=True)
class DistributionSnapshot:
    name: str
    version: str
    metadata_sha256: str
    top_level_modules: tuple[str, ...] = ()
    console_scripts: tuple[ConsoleEntryPoint, ...] = ()


@dataclass(frozen=True)
class RejectedMetadata:
    field: str
    value: str
    reason: str


@dataclass(frozen=True)
class SmokeProbe:
    probe_id: str
    kind: SmokeProbeKind
    argv: tuple[str, ...]
    metadata_sha256: str

    @property
    def semantic_import(self) -> bool:
        return self.kind in {
            SmokeProbeKind.PACKAGE_IMPORT,
            SmokeProbeKind.ENTRY_POINT_IMPORT,
        }


@dataclass(frozen=True)
class SmokePlan:
    distribution: str
    probes: tuple[SmokeProbe, ...]
    rejections: tuple[RejectedMetadata, ...]


@dataclass(frozen=True)
class ProbeOutcome:
    probe_id: str
    exit_code: int | None
    timed_out: bool = False
    duration_seconds: float | None = None
    stdout_sha256: str | None = None
    stderr_sha256: str | None = None


@dataclass(frozen=True)
class SmokeDecision:
    passed: bool | None
    reason: str
    observed_probe_ids: tuple[str, ...]


class SmokeCommandRunner(Protocol):
    def run(
        self,
        probe: SmokeProbe,
        *,
        timeout_seconds: int,
        network_disabled: bool,
        empty_workdir: bool,
    ) -> ProbeOutcome: ...


class MetadataSmokePlanner:
    def plan(self, snapshot: DistributionSnapshot) -> SmokePlan:
        rejections: list[RejectedMetadata] = []
        probes: list[SmokeProbe] = []
        if not snapshot.name.strip():
            rejections.append(RejectedMetadata("name", snapshot.name, "empty distribution name"))
        if not snapshot.version.strip():
            rejections.append(RejectedMetadata("version", snapshot.version, "empty distribution version"))
        if not _HASH.fullmatch(snapshot.metadata_sha256):
            rejections.append(
                RejectedMetadata(
                    "metadata_sha256",
                    snapshot.metadata_sha256,
                    "expected lowercase SHA-256",
                )
            )

        for module in sorted(set(snapshot.top_level_modules)):
            if not _dotted_identifier(module):
                rejections.append(
                    RejectedMetadata("top_level_modules", module, "invalid import name")
                )
                continue
            probes.append(
                SmokeProbe(
                    f"package:{module}",
                    SmokeProbeKind.PACKAGE_IMPORT,
                    ("python", "-I", "-c", _IMPORT_CODE, module),
                    snapshot.metadata_sha256,
                )
            )

        entries_by_name: dict[str, str] = {}
        for entry in sorted(snapshot.console_scripts, key=lambda item: (item.name, item.target)):
            previous = entries_by_name.get(entry.name)
            if previous is not None and previous != entry.target:
                rejections.append(
                    RejectedMetadata(
                        "console_scripts",
                        entry.name,
                        "ambiguous executable target",
                    )
                )
                continue
            entries_by_name[entry.name] = entry.target
            if previous == entry.target:
                continue
            parsed = _entry_point_target(entry.target)
            if not _EXECUTABLE.fullmatch(entry.name):
                rejections.append(
                    RejectedMetadata("console_scripts.name", entry.name, "invalid executable name")
                )
                continue
            if parsed is None:
                rejections.append(
                    RejectedMetadata("console_scripts.target", entry.target, "invalid object reference")
                )
                continue
            module, attributes = parsed
            probes.extend(
                (
                    SmokeProbe(
                        f"entry:{entry.name}:import",
                        SmokeProbeKind.ENTRY_POINT_IMPORT,
                        ("python", "-I", "-c", _ENTRY_POINT_CODE, module, attributes),
                        snapshot.metadata_sha256,
                    ),
                    SmokeProbe(
                        f"entry:{entry.name}:cli",
                        SmokeProbeKind.CLI_RESOLUTION,
                        ("python", "-I", "-c", _CLI_RESOLUTION_CODE, entry.name),
                        snapshot.metadata_sha256,
                    ),
                )
            )
        return SmokePlan(snapshot.name, tuple(probes), tuple(rejections))


def decide_smoke(plan: SmokePlan, outcomes: Iterable[ProbeOutcome]) -> SmokeDecision:
    outcome_list = tuple(outcomes)
    identifiers = [item.probe_id for item in outcome_list]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate smoke outcome")
    planned = {item.probe_id for item in plan.probes}
    unknown = set(identifiers) - planned
    if unknown:
        raise ValueError(f"outcome for unplanned probe: {sorted(unknown)[0]}")
    observed = tuple(sorted(identifiers))
    if any(item.timed_out or (item.exit_code is not None and item.exit_code != 0) for item in outcome_list):
        return SmokeDecision(False, "observed probe failure", observed)
    if plan.rejections:
        return SmokeDecision(None, "metadata rejected", observed)
    if not any(item.semantic_import for item in plan.probes):
        return SmokeDecision(None, "no semantic import probe", observed)
    if planned != set(identifiers) or any(item.exit_code is None for item in outcome_list):
        return SmokeDecision(None, "probe outcome missing", observed)
    return SmokeDecision(True, "all metadata-derived probes passed", observed)


def execute_smoke_plan(
    plan: SmokePlan,
    runner: SmokeCommandRunner,
    timeout_seconds: int = 30,
) -> tuple[tuple[ProbeOutcome, ...], SmokeDecision]:
    if timeout_seconds <= 0:
        raise ValueError("smoke timeout must be positive")
    outcomes = []
    for probe in plan.probes:
        outcome = runner.run(
            probe,
            timeout_seconds=timeout_seconds,
            network_disabled=True,
            empty_workdir=True,
        )
        if outcome.probe_id != probe.probe_id:
            raise ValueError("runner returned outcome for a different probe")
        outcomes.append(outcome)
    frozen = tuple(outcomes)
    return frozen, decide_smoke(plan, frozen)


def _dotted_identifier(value: str) -> bool:
    parts = value.split(".")
    return bool(parts) and all(part.isidentifier() and not keyword.iskeyword(part) for part in parts)


def _entry_point_target(value: str) -> tuple[str, str] | None:
    reference = value.split("[", 1)[0].strip()
    if reference.count(":") != 1:
        return None
    module, attributes = (item.strip() for item in reference.split(":", 1))
    if not _dotted_identifier(module) or not _dotted_identifier(attributes):
        return None
    return module, attributes
