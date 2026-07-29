import inspect

from envsolve_harness.runners.envsolve_pro import (
    METHOD as FROZEN_METHOD,
    EnvSolveProRunner,
)
from envsolve_harness.runners.envsolve_pro_execution_feedback import (
    METHOD,
    METHOD_PROFILE,
    EnvSolveProExecutionFeedbackRunner,
)
from envsolve_harness.runners.frontier_experiment import FrontierExperimentRunner


def test_execution_feedback_runner_isolated_from_frozen_baseline() -> None:
    assert FROZEN_METHOD == "envsolve-pro-operation-contract"
    assert "run_envsolve_operation_episode.py" in inspect.getsource(
        EnvSolveProRunner.run
    )

    assert METHOD == "envsolve-pro-execution-feedback-v3"
    assert METHOD_PROFILE["constraint_profile"] == "goal-obligation-frontier-v1"
    assert METHOD_PROFILE["execution_feedback_profile"] == (
        "observable-recoverable-v3"
    )
    assert METHOD_PROFILE["bootstrap_taxonomy"] == "disabled"
    assert issubclass(
        EnvSolveProExecutionFeedbackRunner,
        FrontierExperimentRunner,
    )
    assert EnvSolveProExecutionFeedbackRunner.episode_tool == (
        "run_envsolve_execution_feedback_episode.py"
    )
