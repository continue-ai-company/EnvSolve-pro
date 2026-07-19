from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", value).strip("._")


@dataclass(frozen=True)
class RunArtifacts:
    root: Path

    @classmethod
    def create(
        cls,
        runs_root: Path,
        run_id: str,
        case_id: str,
        overwrite: bool = False,
    ) -> "RunArtifacts":
        root = runs_root / safe_name(run_id) / safe_name(case_id)
        if root.exists() and any(root.iterdir()):
            if not overwrite:
                raise FileExistsError(f"Run artifacts already exist: {root}. Pass --overwrite to replace them.")
            shutil.rmtree(root)
        for child in ("inputs", "scripts", "generation", "evaluation", "logs", "runtime"):
            (root / child).mkdir(parents=True, exist_ok=True)
        return cls(root=root)

    @property
    def manifest(self) -> Path:
        return self.root / "manifest.json"

    @property
    def case_input(self) -> Path:
        return self.root / "inputs" / "case.json"

    @property
    def benchmark_input(self) -> Path:
        return self.root / "inputs" / "evaluator.jsonl"

    @property
    def solver_input(self) -> Path:
        return self.root / "inputs" / "solver.jsonl"

    @property
    def bootstrap_script(self) -> Path:
        return self.root / "scripts" / "bootstrap.sh"

    @property
    def evaluation_dir(self) -> Path:
        return self.root / "evaluation"

    @property
    def generation_dir(self) -> Path:
        return self.root / "generation"

    @property
    def generated_script(self) -> Path:
        return self.root / "scripts" / "generated.sh"

    @property
    def solver_result(self) -> Path:
        return self.root / "generation" / "result.json"

    @property
    def budget_ledger(self) -> Path:
        return self.root / "generation" / "budget_ledger.json"

    @property
    def episode_event_log(self) -> Path:
        return self.root / "generation" / "episode.jsonl"

    @property
    def episode_snapshot(self) -> Path:
        return self.root / "generation" / "episode_snapshot.json"

    @property
    def raw_artifacts(self) -> Path:
        return self.root / "generation" / "raw-artifacts"

    @property
    def solver_log(self) -> Path:
        return self.root / "logs" / "solver.log"

    @property
    def trajectory(self) -> Path:
        return self.root / "generation" / "trajectory.json"

    @property
    def trajectory_jsonl(self) -> Path:
        return self.root / "generation" / "trajectory.jsonl"

    @property
    def evaluation_log(self) -> Path:
        return self.root / "logs" / "evaluation.log"

    @property
    def evaluation_claim(self) -> Path:
        return self.root / "evaluation" / "official_attempt.json"

    @property
    def parsed_result(self) -> Path:
        return self.root / "evaluation" / "result.json"

    @property
    def status(self) -> Path:
        return self.root / "status.json"

    @property
    def runtime_heartbeat(self) -> Path:
        return self.root / "runtime" / "heartbeat.jsonl"
