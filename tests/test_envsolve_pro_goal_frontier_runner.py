import inspect

from envsolve_harness.runners.envsolve_pro import (
    METHOD as FROZEN_METHOD,
    METHOD_PROFILE as FROZEN_METHOD_PROFILE,
    EnvSolveProRunner,
)
from envsolve_harness.runners.envsolve_pro_goal_frontier import (
    METHOD,
    METHOD_PROFILE,
    EnvSolveProGoalFrontierRunner,
)


def test_goal_frontier_runner_is_isolated_from_frozen_operation_contract() -> None:
    assert FROZEN_METHOD == "envsolve-pro-operation-contract"
    assert FROZEN_METHOD_PROFILE["operation_profile"] == "evidence-directed"
    assert "run_envsolve_operation_episode.py" in inspect.getsource(
        EnvSolveProRunner.run
    )

    assert METHOD == "envsolve-pro-goal-frontier"
    assert METHOD_PROFILE["constraint_profile"] == (
        "goal-obligation-frontier-v1"
    )
    assert METHOD_PROFILE["operation_profile"] == "open-program"
    assert EnvSolveProGoalFrontierRunner.episode_tool == (
        "run_envsolve_goal_frontier_episode.py"
    )
