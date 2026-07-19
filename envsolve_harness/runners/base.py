from __future__ import annotations

from typing import Protocol

from envsolve_harness.core.models import Case, RunSpec, SolverResult
from envsolve_harness.storage.artifacts import RunArtifacts


class SolverRunner(Protocol):
    def run(self, case: Case, artifacts: RunArtifacts, run_spec: RunSpec) -> SolverResult: ...

