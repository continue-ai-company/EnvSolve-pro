from __future__ import annotations

from collections import defaultdict
from typing import Any

from envsolve.operations import OperationGuardDecision
from envsolve.operations.planner import ConstraintOperationPlanner
from envsolve.solver import DeploymentCandidate
from envsolve.state import EnvironmentState
from envsolve_harness.scripts.replay_actions import analyze_successful_command


class ConstraintOperationGuard:
    """Require current obligation coverage and reject known failed execution paths."""

    policy_id = "constraint-operation-guard-v3"

    def __init__(self, planner: ConstraintOperationPlanner | None = None) -> None:
        self.planner = planner or ConstraintOperationPlanner()

    @staticmethod
    def _actions(script: str) -> tuple[tuple[str, str], ...]:
        actions: list[tuple[str, str]] = []
        for line in script.splitlines():
            value = line.strip()
            if not value or value.startswith("#") or value.startswith("set "):
                continue
            analysis = analyze_successful_command(value)
            if analysis.unsupported_reason:
                raise ValueError(
                    f"Operation guard received unsupported command: {analysis.unsupported_reason}"
                )
            actions.extend((item.kind, item.command) for item in analysis.actions)
        return tuple(actions)

    @classmethod
    def _latest_candidate_actions(
        cls, state: EnvironmentState
    ) -> tuple[tuple[str, str], ...]:
        verified_candidate_ids = {
            str(item.get("details", {}).get("candidate_id"))
            for item in state.verifications
            if isinstance(item.get("details"), dict)
            and item["details"].get("candidate_id")
        }
        candidates = [
            item
            for item in state.actions.values()
            if item.get("action_type") == "deployment-candidate"
            and str(item.get("action_id")) in verified_candidate_ids
            and isinstance(item.get("metadata"), dict)
            and isinstance(item["metadata"].get("candidate_validation"), dict)
        ]
        if not candidates:
            return ()
        latest = max(
            candidates,
            key=lambda item: int(
                item.get("state_metadata", {}).get("event_sequence", -1)
            ),
        )
        return cls._actions(str(latest.get("command", "")))

    @staticmethod
    def _commands(script: str) -> tuple[str, ...]:
        return tuple(
            value
            for line in script.splitlines()
            if (value := line.strip())
            and not value.startswith("#")
            and not value.startswith("set ")
        )

    @classmethod
    def _failed_attempts(cls, state: EnvironmentState) -> tuple[dict[str, Any], ...]:
        attempts: list[dict[str, Any]] = []
        for verification in state.verifications:
            if verification.get("passed") is not False:
                continue
            details = verification.get("details")
            if not isinstance(details, dict):
                continue
            candidate_id = str(details.get("candidate_id", ""))
            verifier_details = details.get("verifier_details")
            failed_action = (
                verifier_details.get("failed_candidate_action")
                if isinstance(verifier_details, dict)
                else None
            )
            prefix = (
                failed_action.get("prefix_commands")
                if isinstance(failed_action, dict)
                else None
            )
            if (
                isinstance(prefix, list)
                and prefix
                and all(isinstance(item, str) and item.strip() for item in prefix)
            ):
                attempts.append(
                    {
                        "candidate_id": candidate_id,
                        "mode": "failed-prefix",
                        "commands": tuple(prefix),
                    }
                )
                continue
            action = state.actions.get(candidate_id)
            if not isinstance(action, dict):
                continue
            commands = cls._commands(str(action.get("command", "")))
            if commands:
                attempts.append(
                    {
                        "candidate_id": candidate_id,
                        "mode": "exact-candidate",
                        "commands": commands,
                    }
                )
        return tuple(attempts)

    def validate(
        self,
        candidate: DeploymentCandidate,
        state: EnvironmentState,
    ) -> OperationGuardDecision:
        plan = self.planner.plan(state)
        current = self._actions(candidate.script)
        current_commands = self._commands(candidate.script)
        previous_commands = {
            command for _, command in self._latest_candidate_actions(state)
        }
        current_by_kind: dict[str, set[str]] = defaultdict(set)
        new_by_kind: dict[str, set[str]] = defaultdict(set)
        for kind, command in current:
            current_by_kind[kind].add(command)
            if command not in previous_commands:
                new_by_kind[kind].add(command)

        unmet = []
        for requirement in plan.requirements:
            allowed = {item.value for item in requirement.allowed_operation_kinds}
            if not any(current_by_kind.get(kind) for kind in allowed):
                unmet.append(requirement.requirement_id)
        repeated_attempts = []
        for attempt in self._failed_attempts(state):
            commands = attempt["commands"]
            repeated = (
                current_commands[: len(commands)] == commands
                if attempt["mode"] == "failed-prefix"
                else current_commands == commands
            )
            if repeated:
                repeated_attempts.append(
                    {
                        "candidate_id": attempt["candidate_id"],
                        "mode": attempt["mode"],
                    }
                )
        details: dict[str, Any] = {
            "operation_plan": plan.to_dict(),
            "candidate_actions": [
                {"kind": kind, "command": command} for kind, command in current
            ],
            "covered_actions": {
                kind: sorted(commands)
                for kind, commands in sorted(current_by_kind.items())
            },
            "new_actions": {
                kind: sorted(commands) for kind, commands in sorted(new_by_kind.items())
            },
            "unmet_requirement_ids": unmet,
            "repeated_failed_attempts": repeated_attempts,
        }
        if unmet:
            return OperationGuardDecision(
                False,
                self.policy_id,
                plan,
                reason=(
                    "Candidate does not introduce a permitted new mutation for operation "
                    "requirements: " + ", ".join(unmet)
                ),
                details=details,
            )
        if repeated_attempts:
            return OperationGuardDecision(
                False,
                self.policy_id,
                plan,
                reason="Candidate repeats a previously failed execution path",
                details=details,
            )
        return OperationGuardDecision(True, self.policy_id, plan, details=details)
