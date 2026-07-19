from __future__ import annotations

from envsolve.repairs.engine import RepairConstraintEngine, preflight_repair
from envsolve.repairs.models import ProbeObservation, RepairPlan
from envsolve.solver import ActionSpec, SolverStateSession, StopDecision
from envsolve.state import EnvironmentState


class TypedRepairPolicy:
    def __init__(
        self,
        plan: RepairPlan,
        session: SolverStateSession,
        engine: RepairConstraintEngine | None = None,
    ) -> None:
        self.plan = plan
        self.session = session
        self.engine = engine or RepairConstraintEngine()

    @property
    def _preflight_evidence_id(self) -> str:
        return f"evidence-{self.plan.repair_id}-preflight"

    @property
    def _failure_id(self) -> str:
        return f"failure-{self.plan.repair_id}"

    @property
    def _verification_id(self) -> str:
        return f"verification-{self.plan.repair_id}"

    def _record_preflight_once(self, value: dict[str, object]) -> None:
        if self._preflight_evidence_id in self.session.reconstruct().evidence:
            return
        self.session.record_evidence(
            kind="repair-preflight",
            source="typed-repair-v1",
            value=value,
            evidence_id=self._preflight_evidence_id,
        )

    def _record_failure_once(
        self,
        category: str,
        message: str,
        action_id: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        if self._failure_id in self.session.reconstruct().failures:
            return
        self.session.record_failure(
            category=category,
            message=message,
            action_id=action_id,
            details=details,
            failure_id=self._failure_id,
        )

    def _record_verification_once(
        self,
        passed: bool,
        details: dict[str, object],
    ) -> None:
        state = self.session.reconstruct()
        existing = {
            item.get("verification_id") for item in state.verifications
        }
        if self._verification_id in existing:
            return
        self.session.record_verification(
            level="V1",
            verifier="typed-repair-probe-v1",
            passed=passed,
            details=details,
            verification_id=self._verification_id,
        )

    def _record_observation_once(
        self,
        observation: ProbeObservation,
    ) -> None:
        evidence_id = self.plan.verification_evidence_id
        if evidence_id not in self.session.reconstruct().evidence:
            self.session.record_evidence(
                kind=observation.evidence_kind,
                source=f"typed-repair-probe:{self.plan.repair_id}",
                value=observation.evidence_value,
                evidence_id=evidence_id,
            )
        self.engine.ingest_evidence(self.session, evidence_id)

    def _supersede_replaced_facts(self) -> None:
        for constraint_id in self.plan.supersede_constraint_ids:
            state = self.session.reconstruct()
            record = state.constraints[constraint_id]
            if record["status"] == "superseded":
                continue
            self.session.upsert_constraint(
                constraint_id=constraint_id,
                kind=str(record["kind"]),
                expression=str(record["expression"]),
                status="superseded",
                evidence_ids=list(record["evidence_ids"]),
            )

    def _blocked(
        self,
        category: str,
        message: str,
        action_id: str | None = None,
        details: dict[str, object] | None = None,
    ) -> StopDecision:
        self._record_failure_once(category, message, action_id, details)
        self._record_verification_once(
            False,
            {
                "repair_id": self.plan.repair_id,
                "message": message,
                **(details or {}),
            },
        )
        return StopDecision(message, "blocked")

    def next_step(self, state: EnvironmentState) -> ActionSpec | StopDecision:
        state = self.session.reconstruct()
        replacements_complete = all(
            state.constraints.get(constraint_id, {}).get("status") == "superseded"
            for constraint_id in self.plan.supersede_constraint_ids
        )
        if replacements_complete:
            report = self.engine.propagate(self.session)
            self._record_verification_once(
                True,
                {
                    "repair_id": self.plan.repair_id,
                    "post_state": report.to_dict(),
                },
            )
            return StopDecision("typed repair verified", "satisfied")

        mutation = state.actions.get(self.plan.mutation_action_id)
        if mutation is None:
            preflight = preflight_repair(state, self.plan, self.engine)
            self._record_preflight_once(
                {
                    "repair": self.plan.to_dict(),
                    "result": preflight.to_dict(),
                }
            )
            if not preflight.allowed:
                return self._blocked(
                    "repair-preflight-reject",
                    "; ".join(preflight.reasons),
                    details={"preflight": preflight.to_dict()},
                )
            return self.plan.mutation_action()
        if mutation.get("status") != "succeeded":
            return self._blocked(
                "repair-mutation-failed",
                "Typed repair mutation did not succeed",
                action_id=self.plan.mutation_action_id,
                details={
                    "status": str(mutation.get("status")),
                    "exit_code": mutation.get("exit_code"),
                },
            )

        verification = state.actions.get(self.plan.verification_action_id)
        if verification is None:
            return self.plan.verification_action()
        try:
            observation = self.plan.probe.parse_action(verification)
        except ValueError as exc:
            return self._blocked(
                "repair-verification-unparseable",
                str(exc),
                action_id=self.plan.verification_action_id,
            )
        self._record_observation_once(observation)
        expected = self.plan.proposed_fact.semantic_dict()
        observed = observation.fact.semantic_dict()
        if verification.get("status") != "succeeded" or observed != expected:
            return self._blocked(
                "repair-verification-mismatch",
                "Repair verification did not observe the proposed fact",
                action_id=self.plan.verification_action_id,
                details={"expected": expected, "observed": observed},
            )

        self._supersede_replaced_facts()
        report = self.engine.propagate(self.session)
        remaining = set(self.plan.source_conflict_ids) & {
            item.conflict_id for item in report.conflicts
        }
        if remaining:
            return self._blocked(
                "repair-postcondition-conflict",
                "Source conflict remains after verified repair",
                action_id=self.plan.verification_action_id,
                details={
                    "remaining_conflict_ids": sorted(remaining),
                    "post_state": report.to_dict(),
                },
            )
        self._record_verification_once(
            True,
            {
                "repair_id": self.plan.repair_id,
                "observed": observed,
                "post_state": report.to_dict(),
            },
        )
        return StopDecision("typed repair verified", "satisfied")
