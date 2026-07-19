from __future__ import annotations

from envsolve.repairs import RepairConstraintEngine, RepairPlan, preflight_repair
from envsolve.solver import ActionSpec, SolverStateSession, StopDecision
from envsolve.state import EnvironmentState


class SemanticCapabilityRepairPolicy:
    def __init__(
        self,
        plan: RepairPlan,
        session: SolverStateSession,
        semantic_probe_command: str,
        engine: RepairConstraintEngine | None = None,
    ) -> None:
        self.plan = plan
        self.session = session
        self.engine = engine or RepairConstraintEngine()
        if not semantic_probe_command.strip() or "\n" in semantic_probe_command:
            raise ValueError("Semantic capability probe must be one non-empty command")
        self.semantic_probe_command = semantic_probe_command
        if plan.kind.value != "system_capability_install":
            raise ValueError("Semantic capability policy requires a capability plan")

    @property
    def semantic_action_id(self) -> str:
        return f"{self.plan.repair_id}-semantic-v2"

    @property
    def verification_id(self) -> str:
        return f"verification-v2-{self.plan.repair_id}"

    @property
    def failure_id(self) -> str:
        return f"failure-v2-{self.plan.repair_id}"

    def _verify_once(self, passed: bool, details: dict[str, object]) -> None:
        if self.verification_id in {
            item.get("verification_id") for item in self.session.reconstruct().verifications
        }:
            return
        self.session.record_verification(
            level="V2",
            verifier="semantic-capability-version-v1",
            passed=passed,
            details={"repair_id": self.plan.repair_id, **details},
            verification_id=self.verification_id,
        )

    def _blocked(self, message: str, action_id: str) -> StopDecision:
        if self.failure_id not in self.session.reconstruct().failures:
            self.session.record_failure(
                category="semantic-capability-verification-failed",
                message=message,
                action_id=action_id,
                details={"repair_id": self.plan.repair_id},
                failure_id=self.failure_id,
            )
        self._verify_once(False, {"message": message})
        return StopDecision(message, "blocked")

    def _supersede(self) -> None:
        for constraint_id in self.plan.supersede_constraint_ids:
            record = self.session.reconstruct().constraints[constraint_id]
            if record["status"] == "superseded":
                continue
            self.session.upsert_constraint(
                constraint_id=constraint_id,
                kind=str(record["kind"]),
                expression=str(record["expression"]),
                status="superseded",
                evidence_ids=list(record["evidence_ids"]),
            )

    def next_step(self, state: EnvironmentState) -> ActionSpec | StopDecision:
        state = self.session.reconstruct()
        if all(
            state.constraints[item]["status"] == "superseded"
            for item in self.plan.supersede_constraint_ids
        ):
            return StopDecision("semantic capability repair verified", "satisfied")
        mutation = state.actions.get(self.plan.mutation_action_id)
        if mutation is None:
            preflight = preflight_repair(state, self.plan, self.engine)
            if not preflight.allowed:
                return self._blocked(
                    "; ".join(preflight.reasons),
                    self.plan.mutation_action_id,
                )
            evidence_id = f"evidence-v2-{self.plan.repair_id}-preflight"
            if evidence_id not in state.evidence:
                self.session.record_evidence(
                    "repair-preflight",
                    "semantic-capability-repair-v1",
                    preflight.to_dict(),
                    evidence_id=evidence_id,
                )
            return self.plan.mutation_action()
        if mutation.get("status") != "succeeded":
            return self._blocked("Capability mutation failed", self.plan.mutation_action_id)
        presence = state.actions.get(self.plan.verification_action_id)
        if presence is None:
            return self.plan.verification_action()
        try:
            observation = self.plan.probe.parse_action(presence)
        except ValueError as exc:
            return self._blocked(str(exc), self.plan.verification_action_id)
        if (
            presence.get("status") != "succeeded"
            or observation.fact.semantic_dict()
            != self.plan.proposed_fact.semantic_dict()
        ):
            return self._blocked(
                "V1 capability presence did not match the proposed fact",
                self.plan.verification_action_id,
            )
        semantic = state.actions.get(self.semantic_action_id)
        if semantic is None:
            return ActionSpec(
                action_type="probe",
                command=self.semantic_probe_command,
                rationale="Verify the executable capability interface",
                action_id=self.semantic_action_id,
                metadata={
                    "mutates_environment": False,
                    "verification_level": "V2",
                    "capability": self.plan.proposed_fact.subject,
                    "interface_contract": self.semantic_probe_command,
                },
            )
        output = semantic.get("observation")
        stdout = str(output.get("stdout", "")) if isinstance(output, dict) else ""
        if semantic.get("status") != "succeeded" or not stdout.strip():
            return self._blocked(
                "V2 capability interface probe failed",
                self.semantic_action_id,
            )
        semantic_evidence_id = f"evidence-v2-{self.plan.repair_id}-semantic"
        if semantic_evidence_id not in state.evidence:
            self.session.record_evidence(
                "capability-interface-observation",
                "semantic-capability-version-v1",
                {
                    "name": self.plan.proposed_fact.subject,
                    "interface": self.semantic_probe_command,
                    "output": stdout.strip(),
                },
                evidence_id=semantic_evidence_id,
            )
        presence_evidence_id = self.plan.verification_evidence_id
        if presence_evidence_id not in self.session.reconstruct().evidence:
            self.session.record_evidence(
                observation.evidence_kind,
                f"semantic-capability-v1:{self.plan.repair_id}",
                observation.evidence_value,
                evidence_id=presence_evidence_id,
            )
        self.engine.ingest_evidence(self.session, presence_evidence_id)
        self._supersede()
        report = self.engine.propagate(self.session)
        if set(self.plan.source_conflict_ids) & {
            item.conflict_id for item in report.conflicts
        }:
            return self._blocked(
                "Source conflict remains after V2 verification",
                self.semantic_action_id,
            )
        self._verify_once(
            True,
            {"semantic_output": stdout.strip(), "post_state": report.to_dict()},
        )
        return StopDecision("semantic capability repair verified", "satisfied")
