from __future__ import annotations

from envsolve_harness.runners.frontier_experiment import (
    FrontierExperimentRunner,
)


METHOD = "envsolve-pro-bootstrap-frontier-v2"
METHOD_PROFILE = {
    "obligation_profile": "goal-contract",
    "operation_profile": "open-program",
    "base_operation_profile": "free-form",
    "constraint_profile": "bootstrap-contradiction-frontier-v2",
    "goal_frontier_profile": "goal-obligation-frontier-v1",
    "base_constraint_profile": "flat",
    "repository_evidence_profile": "constraint-routed",
    "candidate_anchor_profile": "retained-admissible",
    "candidate_interface": "open-program",
    "candidate_retention": "best-admissible",
    "environment_strategy": "fresh-candidate",
    "base_environment_observation": "model-visible",
}


class EnvSolveProBootstrapFrontierRunner(FrontierExperimentRunner):
    """Launcher for the bootstrap-contradiction frontier treatment."""

    method = METHOD
    method_profile = METHOD_PROFILE
    runner_id = "envsolve-pro-bootstrap-frontier"
    runner_version = "0.1.0"
    episode_tool = "run_envsolve_bootstrap_frontier_episode.py"
