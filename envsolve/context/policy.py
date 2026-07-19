from __future__ import annotations

from envsolve.context.probes import (
    DEFAULT_CONTEXT_PROBES,
    PYENV_INVENTORY,
    PYENV_PRESENCE,
    PYENV_ROOT,
    ContextProbe,
)
from envsolve.solver import ActionSpec, SolverStateSession, StopDecision
from envsolve.state import EnvironmentState


class ContextAcquisitionPolicy:
    def __init__(
        self,
        session: SolverStateSession,
        probes: tuple[ContextProbe, ...] = DEFAULT_CONTEXT_PROBES,
    ) -> None:
        self.session = session
        self.probes = probes

    @staticmethod
    def _pyenv_present(state: EnvironmentState) -> bool | None:
        evidence = state.evidence.get(PYENV_PRESENCE.evidence_id)
        if evidence is None:
            return None
        value = evidence.get("value")
        if not isinstance(value, dict) or not isinstance(value.get("present"), bool):
            raise ValueError("Recorded pyenv context evidence is invalid")
        return bool(value["present"])

    def _record_probe(self, probe: ContextProbe, action: dict) -> None:
        if probe.evidence_id in self.session.reconstruct().evidence:
            return
        kind, value = probe.parse_action(action)
        self.session.record_evidence(
            kind=kind,
            source=f"context-probe:{probe.probe_id}",
            value=value,
            evidence_id=probe.evidence_id,
        )

    def _blocked(self, probe: ContextProbe, message: str) -> StopDecision:
        state = self.session.reconstruct()
        failure_id = f"failure-context-{probe.probe_id}"
        if failure_id not in state.failures:
            self.session.record_failure(
                category="context-probe-failed",
                message=message,
                action_id=probe.action_id if probe.action_id in state.actions else None,
                details={"probe_id": probe.probe_id},
                failure_id=failure_id,
            )
        return StopDecision(message, "blocked")

    def next_step(self, state: EnvironmentState) -> ActionSpec | StopDecision:
        state = self.session.reconstruct()
        for probe in self.probes:
            if probe in {PYENV_ROOT, PYENV_INVENTORY}:
                pyenv_present = self._pyenv_present(state)
                if pyenv_present is None:
                    continue
                if not pyenv_present:
                    continue
            action = state.actions.get(probe.action_id)
            if action is None:
                return probe.action()
            if action.get("status") != "succeeded":
                return self._blocked(
                    probe,
                    f"Context probe {probe.probe_id} did not succeed",
                )
            try:
                self._record_probe(probe, action)
            except ValueError as exc:
                return self._blocked(probe, str(exc))
            state = self.session.reconstruct()
        return StopDecision("context acquisition complete", "satisfied")
