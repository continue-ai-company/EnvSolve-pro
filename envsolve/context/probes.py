from __future__ import annotations

from dataclasses import dataclass
import re
import shlex
from typing import Any

from packaging.version import InvalidVersion, Version

from envsolve.context.models import ContextProbeKind, validate_name, validate_path
from envsolve.solver import ActionSpec


PRESENCE_LINE = re.compile(r"^(present)(?:\t(.+))?$|^(absent)$")


def _presence_command(name: str) -> str:
    validated = validate_name(name, "probe tool")
    quoted = shlex.quote(validated)
    return (
        f"if p=$(command -v -- {quoted}); then "
        "printf 'present\\t%s\\n' \"$p\"; "
        "else printf 'absent\\n'; fi"
    )


@dataclass(frozen=True)
class ContextProbe:
    probe_id: str
    kind: ContextProbeKind
    subject: str
    command: str

    @property
    def action_id(self) -> str:
        return f"context-{self.probe_id}"

    @property
    def evidence_id(self) -> str:
        return f"evidence-context-{self.probe_id}"

    def action(self) -> ActionSpec:
        return ActionSpec(
            action_type="probe",
            command=self.command,
            rationale=f"Acquire context evidence for {self.subject}",
            action_id=self.action_id,
            metadata={
                "mutates_environment": False,
                "context_probe": {
                    "probe_id": self.probe_id,
                    "kind": self.kind.value,
                    "subject": self.subject,
                },
            },
        )

    def parse_action(self, action: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        if action.get("status") != "succeeded" or action.get("exit_code") != 0:
            raise ValueError(f"Context probe {self.probe_id} did not succeed")
        observation = action.get("observation")
        if not isinstance(observation, dict):
            raise ValueError(f"Context probe {self.probe_id} has no observation")
        stdout = str(observation.get("stdout", ""))
        if self.kind in {
            ContextProbeKind.TOOL_PRESENCE,
            ContextProbeKind.SYSTEM_MANAGER_PRESENCE,
        }:
            lines = [line.strip() for line in stdout.splitlines() if line.strip()]
            if len(lines) != 1:
                raise ValueError(
                    f"Context presence probe {self.probe_id} emitted invalid output"
                )
            match = PRESENCE_LINE.fullmatch(lines[0])
            if match is None:
                raise ValueError(
                    f"Context presence probe {self.probe_id} emitted invalid output"
                )
            present = match.group(1) == "present"
            path = validate_path(match.group(2), present)
            if self.kind == ContextProbeKind.TOOL_PRESENCE:
                return (
                    "context-tool-observation",
                    {"tool": self.subject, "present": present, "path": path},
                )
            return (
                "context-system-manager-observation",
                {"manager": self.subject, "present": present, "path": path},
            )
        if self.kind == ContextProbeKind.RUNTIME_ROOT:
            lines = [line.strip() for line in stdout.splitlines() if line.strip()]
            if len(lines) != 1:
                raise ValueError(f"Context runtime root probe {self.probe_id} emitted invalid output")
            return (
                "context-runtime-root",
                {"manager": self.subject, "root": validate_path(lines[0], True)},
            )
        versions: set[str] = set()
        for line in stdout.splitlines():
            candidate = line.strip()
            if not candidate:
                continue
            try:
                versions.add(str(Version(candidate)))
            except InvalidVersion:
                continue
        return (
            "context-runtime-inventory",
            {
                "manager": self.subject,
                "versions": sorted(versions, key=Version),
            },
        )


PYENV_PRESENCE = ContextProbe(
    probe_id="tool-pyenv",
    kind=ContextProbeKind.TOOL_PRESENCE,
    subject="pyenv",
    command=_presence_command("pyenv"),
)
PYENV_INVENTORY = ContextProbe(
    probe_id="runtime-pyenv-versions",
    kind=ContextProbeKind.RUNTIME_INVENTORY,
    subject="pyenv",
    command="pyenv versions --bare",
)
PYENV_ROOT = ContextProbe(
    probe_id="runtime-pyenv-root",
    kind=ContextProbeKind.RUNTIME_ROOT,
    subject="pyenv",
    command="pyenv root",
)
SYSTEM_MANAGER_PROBES = tuple(
    ContextProbe(
        probe_id=f"system-manager-{manager}",
        kind=ContextProbeKind.SYSTEM_MANAGER_PRESENCE,
        subject=manager,
        command=_presence_command(manager),
    )
    for manager in ("apt-get", "apk", "dnf", "yum", "brew")
)
DEFAULT_CONTEXT_PROBES = (
    PYENV_PRESENCE,
    PYENV_ROOT,
    PYENV_INVENTORY,
    *SYSTEM_MANAGER_PROBES,
)
