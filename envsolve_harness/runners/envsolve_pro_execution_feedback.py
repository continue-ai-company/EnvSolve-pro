from __future__ import annotations

from envsolve_harness.runners.frontier_experiment import FrontierExperimentRunner


METHOD = "envsolve-pro-execution-feedback-v3"
METHOD_PROFILE = {
    "obligation_profile": "goal-contract",
    "operation_profile": "open-program",
    "base_operation_profile": "free-form",
    "constraint_profile": "goal-obligation-frontier-v1",
    "base_constraint_profile": "flat",
    "repository_evidence_profile": "constraint-routed",
    "candidate_anchor_profile": "retained-admissible",
    "candidate_interface": "open-program",
    "candidate_retention": "best-admissible",
    "environment_strategy": "fresh-candidate",
    "execution_feedback_profile": "observable-recoverable-v3",
    "bootstrap_taxonomy": "disabled",
}


class EnvSolveProExecutionFeedbackRunner(FrontierExperimentRunner):
    """Launcher for observable and recoverable execution feedback."""

    method = METHOD
    method_profile = METHOD_PROFILE
    runner_id = "envsolve-pro-execution-feedback"
    runner_version = "0.1.0"
    episode_tool = "run_envsolve_execution_feedback_episode.py"
