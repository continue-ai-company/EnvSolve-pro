from __future__ import annotations

import re
import shlex
from typing import Any

from envsolve.context.models import normalize_packages, validate_name, validate_path
from envsolve.discovery.apt_file import ProviderEnvironment, parse_provider_environment
from envsolve.discovery.ubuntu_packages import (
    UbuntuContentsDiscovery,
    build_ubuntu_contents_command,
    parse_ubuntu_contents_response,
)
from envsolve.solver import ActionSpec, SolverStateSession, StopDecision
from envsolve.state import EnvironmentState


ENVIRONMENT_COMMAND = (
    "printf 'path\\t%s\\n' \"$PATH\"; "
    "printf 'architecture\\t'; dpkg --print-architecture; "
    ". /etc/os-release; printf 'os\\t%s\\t%s\\n' \"$ID\" "
    "\"${VERSION_CODENAME:-unknown}\""
)


def _presence_command(name: str) -> str:
    quoted = shlex.quote(validate_name(name, "tool"))
    return (
        f"if p=$(command -v -- {quoted}); then printf 'present\\t%s\\n' \"$p\"; "
        "else printf 'absent\\n'; fi"
    )


def _apt_cache_command(packages: tuple[str, ...]) -> str:
    normalized = tuple(normalize_packages(list(packages)))
    commands = []
    for package in normalized:
        quoted = shlex.quote(package)
        commands.append(
            "if apt-cache show --no-all-versions "
            f"{quoted} >/dev/null 2>&1; then printf 'present\\t%s\\n' {quoted}; "
            f"else printf 'absent\\t%s\\n' {quoted}; fi"
        )
    return "; ".join(commands)


def _action(action_id: str, command: str, rationale: str, mutates: bool) -> ActionSpec:
    return ActionSpec(
        action_type="context_provider" if mutates else "probe",
        command=command,
        rationale=rationale,
        action_id=action_id,
        metadata={
            "mutates_environment": mutates,
            "provider": "ubuntu-packages-contents-v1",
        },
    )


class UbuntuPackagesDiscoveryPolicy:
    def __init__(
        self,
        session: SolverStateSession,
        capability: str,
        timeout_seconds: int,
        max_response_bytes: int,
        user_agent: str,
    ) -> None:
        self.session = session
        self.capability = validate_name(capability, "capability")
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.user_agent = user_agent
        suffix = re.sub(r"[^A-Za-z0-9_.-]+", "-", self.capability)
        self.prefix = f"packages-discovery-{suffix}"

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
            source=f"ubuntu-packages-discovery:{self.capability}",
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
                details={
                    "capability": self.capability,
                    "provider": "ubuntu-packages-contents",
                },
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

    def _presence(self, action: dict[str, Any]) -> dict[str, Any]:
        lines = [line for line in self._stdout(action).splitlines() if line.strip()]
        if len(lines) != 1:
            raise ValueError("Capability presence observation is invalid")
        fields = lines[0].split("\t")
        if fields == ["absent"]:
            return {"present": False, "path": None}
        if len(fields) == 2 and fields[0] == "present":
            return {"present": True, "path": validate_path(fields[1], True)}
        raise ValueError("Capability presence observation is invalid")

    def _environment(self, state: EnvironmentState) -> ProviderEnvironment | None:
        action = self._completed(state, "environment")
        if action is None:
            return None
        environment = parse_provider_environment(self._stdout(action))
        self._record_once(
            "environment",
            "provider-environment-observation",
            environment.to_dict(),
        )
        return environment

    def _discovery(
        self,
        state: EnvironmentState,
        environment: ProviderEnvironment,
    ) -> UbuntuContentsDiscovery | None:
        action = self._completed(state, "query")
        if action is None:
            return None
        discovery = parse_ubuntu_contents_response(
            self._stdout(action),
            self.capability,
            environment,
            self.max_response_bytes,
        )
        self._record_once(
            "response-provenance",
            "provider-response-provenance",
            discovery.response.provenance(),
        )
        self._record_once(
            "query-details",
            "provider-capability-discovery",
            discovery.to_dict(),
        )
        return discovery

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
            presence_action = self._completed(state, "capability-presence")
            if presence_action is None:
                return _action(
                    self._id("capability-presence"),
                    _presence_command(self.capability),
                    f"Confirm that {self.capability} is initially absent",
                    False,
                )
            presence = self._presence(presence_action)
            self._record_once(
                "capability-presence",
                "provider-initial-capability-observation",
                {"capability": self.capability, **presence},
            )
            if presence["present"]:
                return self._blocked(
                    f"Capability {self.capability} is already present",
                    self._id("capability-presence"),
                )
            update_action = self._completed(state, "apt-update")
            if update_action is None:
                return _action(
                    self._id("apt-update"),
                    "apt-get update",
                    "Refresh local apt installability metadata",
                    True,
                )
            discovery = self._discovery(state, environment)
            if discovery is None:
                return _action(
                    self._id("query"),
                    build_ubuntu_contents_command(
                        self.capability,
                        environment.codename,
                        environment.architecture,
                        self.timeout_seconds,
                        self.max_response_bytes,
                        self.user_agent,
                    ),
                    f"Query the official exact Contents index for {self.capability}",
                    False,
                )
            if not discovery.candidates:
                return self._blocked(
                    f"No PATH-reachable Ubuntu package provides {self.capability}",
                    self._id("query"),
                )
            cache_action = self._completed(state, "apt-cache")
            if cache_action is None:
                return _action(
                    self._id("apt-cache"),
                    _apt_cache_command(discovery.packages),
                    "Verify discovered packages in the local apt cache",
                    False,
                )
            available: set[str] = set()
            for line in self._stdout(cache_action).splitlines():
                fields = line.strip().split("\t")
                if len(fields) != 2 or fields[0] not in {"present", "absent"}:
                    raise ValueError("Apt-cache verification output is invalid")
                package = normalize_packages([fields[1]])[0]
                if fields[0] == "present":
                    available.add(package)
            verified = tuple(
                candidate
                for candidate in discovery.candidates
                if candidate.package in available
            )
            self._record_once(
                "apt-cache",
                "provider-package-availability",
                {
                    "manager": "apt-get",
                    "available": sorted(available),
                    "queried": list(discovery.packages),
                },
            )
            if not verified:
                return self._blocked(
                    "No discovered package is available in the local apt cache",
                    self._id("apt-cache"),
                )
            packages = tuple(normalize_packages([item.package for item in verified]))
            self._record_once(
                "capability-packages",
                "context-capability-package-candidate",
                {
                    "capability": self.capability,
                    "manager": "apt-get",
                    "packages": list(packages),
                },
            )
            return StopDecision("capability package discovery complete", "satisfied")
        except ValueError as exc:
            return self._blocked(str(exc))
