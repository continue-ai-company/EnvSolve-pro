from __future__ import annotations

from pathlib import Path
from typing import Protocol

from envsolve_harness.core.models import Case, EvaluationResult, RunSpec
from envsolve_harness.storage.artifacts import RunArtifacts
from envsolve.runtime.goal import ExecutableGoalContract
from envsolve.runtime.workspace import WorkspacePrecondition


class BenchmarkAdapter(Protocol):
    @property
    def benchmark_id(self) -> str: ...

    @property
    def workspace_preconditions(self) -> tuple[WorkspacePrecondition, ...]: ...

    @property
    def goal_contract(self) -> ExecutableGoalContract | None: ...

    def evaluate(
        self,
        case: Case,
        script_path: Path,
        artifacts: RunArtifacts,
        run_spec: RunSpec,
    ) -> EvaluationResult: ...
