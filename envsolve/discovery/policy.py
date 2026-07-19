from __future__ import annotations

import re
import shlex
from typing import Any

from envsolve.context.models import validate_name, validate_path
from envsolve.context.providers import apt_file_capability_command
from envsolve.discovery.apt_file import (
    ProviderEnvironment,
    parse_apt_file_discovery,
    parse_provider_environment,
)
from envsolve.solver import ActionSpec, SolverStateSession, StopDecision
from envsolve.state import EnvironmentState


SHA256_LINE = re.compile(r"^([0-9a-f]{64})\s+(.+)$")
ENVIRONMENT_COMMAND = (
    "printf 'path\\t%s\\n' \"$PATH\"; "
    "printf 'architecture\\t'; dpkg --print-architecture; "
    ". /etc/os-release; printf 'os\\t%s\\t%s\\n' \"$ID\" "
    "\"${VERSION_CODENAME:-unknown}\""
)
INDEX_PROVENANCE_COMMAND = (
    "for root in /etc/apt/sources.list /etc/apt/sources.list.d "
    "/var/lib/apt/lists /var/cache/apt-file; do "
    "if [ -e \"$root\" ]; then find \"$root\" -type f -exec sha256sum {} +; fi; "
    "done 2>/dev/null | LC_ALL=C sort"
)


def _presence_command(name: str) -> str:
    quoted = shlex.quote(validate_name(name, "tool"))
    return (
        f"if p=$(command -v -- {quoted}); then printf 'present\\t%s\\n' \"$p\"; "
        "else printf 'absent\\n'; fi"
    )


def _action(
    action_id: str,
    command: str,
    rationale: str,
    mutates: bool,
) -> ActionSpec:
    return ActionSpec(
        action_type="context_provider" if mutates else "probe",
        command=command,
        rationale=rationale,
        action_id=action_id,
        metadata={
            "mutates_environment": mutates,
            "provider": "apt-file-exact-path-on-path-v1",
        },
    )


class AptFileDiscoveryPolicy:
    def __init__(self, session: SolverStateSession, capability: str) -> None:
        self.session = session
        self.capability = validate_name(capability, "capability")
        suffix = re.sub(r"[^A-Za-z0-9_.-]+", "-", self.capability)
        self.prefix = f"discovery-{suffix}"

    def _id(self, name: str) -> str:
        return f"{self.prefix}-{name}"

    def _evidence_id(self, name: str) -> str:
        return f"evidence-{self._id(name)}"

    def _record_once(self, name: str, kind: str, value: Any) -> None:
        evidence_id = self._evidence_id(name)
        if evidence_id in self.session.reconstruct().evidence:
            return
        self.session.record_evidence(
            kind=kind,
            source=f"apt-file-discovery:{self.capability}",
            value=value,
            evidence_id=evidence_id,
        )

    def _blocked(self, message: str, action_id: str | None = None) -> StopDecision:
        failure_id = f"failure-{self.prefix}"
        if failure_id not in self.session.reconstruct().failures:
            self.session.record_failure(
                category="capability-discovery-failed",
                message=message,
                action_id=action_id,
                details={"capability": self.capability, "provider": "apt-file"},
                failure_id=failure_id,
            )
        return StopDecision(message, "blocked")

    @staticmethod
    def _stdout(action: dict[str, Any]) -> str:
        observation = action.get("observation")
        if not isinstance(observation, dict):
            raise ValueError("Provider action has no observation")
        return str(observation.get("stdout", ""))

    def _completed(self, state: EnvironmentState, name: str) -> dict[str, Any] | None:
        action = state.actions.get(self._id(name))
        if action is not None and action.get("status") != "succeeded":
            raise ValueError(f"Provider action {self._id(name)} did not succeed")
        return action

    def _presence(self, action: dict[str, Any], subject: str) -> dict[str, Any]:
        lines = [line for line in self._stdout(action).splitlines() if line.strip()]
        if len(lines) != 1:
            raise ValueError(f"Presence observation for {subject} is invalid")
        fields = lines[0].split("\t")
        if fields == ["absent"]:
            return {"present": False, "path": None}
        if len(fields) == 2 and fields[0] == "present":
            return {"present": True, "path": validate_path(fields[1], True)}
        raise ValueError(f"Presence observation for {subject} is invalid")

    def _environment(self, state: EnvironmentState) -> ProviderEnvironment | None:
        action = self._completed(state, "environment")
        if action is None:
            return None
        environment = parse_provider_environment(self._stdout(action))
        self._record_once("environment", "provider-environment-observation", environment.to_dict())
        return environment

    def next_step(self, state: EnvironmentState) -> ActionSpec | StopDecision:
        try:
            state = self.session.reconstruct()
            environment = self._environment(state)
            if environment is None:
                return _action(
                    self._id("environment"),
                    ENVIRONMENT_COMMAND,
                    "Observe provider platform and executable search path",
                    False,
                )

            capability_action = self._completed(state, "capability-presence")
            if capability_action is None:
                return _action(
                    self._id("capability-presence"),
                    _presence_command(self.capability),
                    f"Confirm that {self.capability} is initially absent",
                    False,
                )
            capability_presence = self._presence(capability_action, self.capability)
            self._record_once(
                "capability-presence",
                "provider-initial-capability-observation",
                {"capability": self.capability, **capability_presence},
            )
            if capability_presence["present"]:
                return self._blocked(
                    f"Capability {self.capability} is already present",
                    self._id("capability-presence"),
                )

            tool_action = self._completed(state, "tool-presence")
            if tool_action is None:
                return _action(
                    self._id("tool-presence"),
                    _presence_command("apt-file"),
                    "Observe apt-file provider availability",
                    False,
                )
            tool_presence = self._presence(tool_action, "apt-file")
            self._record_once(
                "tool-presence",
                "context-tool-observation",
                {"tool": "apt-file", **tool_presence},
            )

            update_action = self._completed(state, "apt-update")
            if update_action is None:
                return _action(
                    self._id("apt-update"),
                    "apt-get update",
                    "Refresh apt package metadata for capability discovery",
                    True,
                )

            if not tool_presence["present"]:
                install_action = self._completed(state, "tool-install")
                if install_action is None:
                    return _action(
                        self._id("tool-install"),
                        (
                            "DEBIAN_FRONTEND=noninteractive apt-get install -y "
                            "--no-install-recommends -- apt-file"
                        ),
                        "Install the generic apt contents-index provider",
                        True,
                    )

            verified_action = self._completed(state, "tool-verified")
            if verified_action is None:
                return _action(
                    self._id("tool-verified"),
                    _presence_command("apt-file"),
                    "Verify apt-file provider availability",
                    False,
                )
            verified = self._presence(verified_action, "apt-file")
            self._record_once(
                "tool-verified",
                "provider-tool-observation",
                {"tool": "apt-file", **verified},
            )
            if not verified["present"]:
                return self._blocked(
                    "apt-file is unavailable after provider bootstrap",
                    self._id("tool-verified"),
                )

            index_action = self._completed(state, "index-update")
            if index_action is None:
                return _action(
                    self._id("index-update"),
                    "apt-file update",
                    "Refresh the apt contents index",
                    True,
                )

            provenance_action = self._completed(state, "index-provenance")
            if provenance_action is None:
                return _action(
                    self._id("index-provenance"),
                    INDEX_PROVENANCE_COMMAND,
                    "Hash apt source definitions and downloaded indexes",
                    False,
                )
            hashes: list[dict[str, str]] = []
            for line in self._stdout(provenance_action).splitlines():
                match = SHA256_LINE.fullmatch(line.strip())
                if match is None:
                    raise ValueError("Apt index provenance output is invalid")
                hashes.append({"sha256": match.group(1), "path": match.group(2)})
            if not hashes:
                raise ValueError("Apt index provenance is empty")
            self._record_once(
                "index-provenance",
                "provider-index-provenance",
                {"provider": "apt-file", "files": hashes},
            )

            search_action = self._completed(state, "search")
            if search_action is None:
                return _action(
                    self._id("search"),
                    apt_file_capability_command(self.capability),
                    f"Find exact PATH-reachable providers for {self.capability}",
                    False,
                )
            discovery = parse_apt_file_discovery(
                self.capability,
                self._stdout(search_action),
                environment,
            )
            self._record_once(
                "search-details",
                "provider-capability-discovery",
                discovery.to_dict(),
            )
            if not discovery.candidates:
                return self._blocked(
                    f"No PATH-reachable apt package provides {self.capability}",
                    self._id("search"),
                )
            self._record_once(
                "capability-packages",
                "context-capability-package-candidate",
                discovery.context_value(),
            )
            return StopDecision("capability package discovery complete", "satisfied")
        except ValueError as exc:
            return self._blocked(str(exc))
