from __future__ import annotations

from collections import defaultdict
from typing import Any

from envsolve.constraints import (
    ConstraintDomain,
    ConstraintPredicate,
    ConstraintRole,
)
from envsolve.operations import (
    OperationFailureClass,
    OperationGuardDecision,
    parse_operation_feasibility_subject,
)
from envsolve.operations.planner import ConstraintOperationPlanner
from envsolve.solver import DeploymentCandidate
from envsolve.state import EnvironmentState
from envsolve_harness.scripts.replay_actions import (
    ReplayActionKind,
    analyze_successful_command,
)


_CONTEXT_KINDS = {
    OperationFailureClass.PYTHON_PROVIDER_TARGET_UNAVAILABLE.value: {
        ReplayActionKind.VIRTUAL_ENVIRONMENT_CREATE.value,
        ReplayActionKind.PYTHON_PACKAGE_INSTALL.value,
        ReplayActionKind.RUNTIME_CONFIGURE.value,
        ReplayActionKind.ENVIRONMENT_EXPORT.value,
        ReplayActionKind.ENVIRONMENT_ACTIVATE.value,
    },
    OperationFailureClass.SYSTEM_PROVIDER_TARGET_UNAVAILABLE.value: {
        ReplayActionKind.PACKAGE_INDEX_UPDATE.value,
        ReplayActionKind.ENVIRONMENT_EXPORT.value,
    },
}


class ConstraintOperationGuard:
    """Require current obligation coverage and reject known failed execution paths."""

    policy_id = "constraint-operation-guard-v4"

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
    def _operation_context_from_prefix(
        cls,
        prefix_commands: tuple[str, ...],
        failure_class: str,
    ) -> tuple[tuple[str, str], ...] | None:
        relevant_kinds = _CONTEXT_KINDS.get(failure_class)
        if relevant_kinds is None or not prefix_commands:
            return None
        context: list[tuple[str, str]] = []
        for prefix_command in prefix_commands[:-1]:
            analysis = analyze_successful_command(prefix_command)
            if analysis.unsupported_reason:
                return None
            context.extend(
                (action.kind, action.command)
                for action in analysis.actions
                if action.kind in relevant_kinds
            )
        return tuple(context)

    @classmethod
    def _operation_contexts(
        cls,
        script: str,
        command: str,
        failure_class: str,
    ) -> tuple[tuple[tuple[str, str], ...], ...]:
        commands = cls._commands(script)
        return tuple(
            context
            for index, candidate_command in enumerate(commands)
            if candidate_command == command
            and (
                context := cls._operation_context_from_prefix(
                    commands[: index + 1],
                    failure_class,
                )
            )
            is not None
        )

    @staticmethod
    def _failed_operation_prefix(
        state: EnvironmentState,
        candidate_id: str,
        command: str,
    ) -> tuple[str, ...] | None:
        for verification in reversed(state.verifications):
            details = verification.get("details")
            if (
                not isinstance(details, dict)
                or details.get("candidate_id") != candidate_id
            ):
                continue
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
                failed_action is None
                or failed_action.get("command") != command
                or not isinstance(prefix, list)
                or not prefix
                or prefix[-1] != command
                or not all(isinstance(item, str) for item in prefix)
            ):
                continue
            return tuple(prefix)
        return None

    def _infeasible_operations(
        self,
        state: EnvironmentState,
    ) -> tuple[dict[str, Any], ...]:
        failures: list[dict[str, Any]] = []
        for constraint in self.planner.constraint_engine.typed_constraints(state):
            if (
                constraint.domain is not ConstraintDomain.OPERATION
                or constraint.role is not ConstraintRole.FACT
                or constraint.predicate is not ConstraintPredicate.FEASIBLE
                or constraint.value is not False
                or constraint.confidence
                < self.planner.constraint_engine.hard_confidence
                or constraint.scope_id is None
            ):
                continue
            try:
                parsed = parse_operation_feasibility_subject(constraint.subject)
            except ValueError:
                continue
            source_prefix = self._failed_operation_prefix(
                state,
                constraint.scope_id,
                parsed["command"],
            )
            if source_prefix is None:
                continue
            source_context = self._operation_context_from_prefix(
                source_prefix,
                parsed["failure_class"],
            )
            if source_context is None:
                continue
            failures.append(
                {
                    **parsed,
                    "constraint_id": constraint.constraint_id,
                    "source_candidate_id": constraint.scope_id,
                    "source_context": source_context,
                }
            )
        return tuple(failures)

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
        contradicted_operations = []
        for failure in self._infeasible_operations(state):
            current_contexts = self._operation_contexts(
                candidate.script,
                failure["command"],
                failure["failure_class"],
            )
            if failure["source_context"] not in current_contexts:
                continue
            contradicted_operations.append(
                {
                    "command": failure["command"],
                    "constraint_id": failure["constraint_id"],
                    "failure_class": failure["failure_class"],
                    "source_candidate_id": failure["source_candidate_id"],
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
            "contradicted_operations": contradicted_operations,
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
        if contradicted_operations:
            return OperationGuardDecision(
                False,
                self.policy_id,
                plan,
                reason="Candidate repeats a grounded infeasible operation",
                details=details,
            )
        return OperationGuardDecision(True, self.policy_id, plan, details=details)
