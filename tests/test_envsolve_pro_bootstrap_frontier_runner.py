import inspect

from envsolve_harness.runners.envsolve_pro import (
    METHOD as FROZEN_METHOD,
    EnvSolveProRunner,
)
from envsolve_harness.runners.envsolve_pro_bootstrap_frontier import (
    METHOD,
    METHOD_PROFILE,
    EnvSolveProBootstrapFrontierRunner,
)
from envsolve_harness.runners.frontier_experiment import (
    FrontierExperimentRunner,
)


def test_bootstrap_frontier_runner_isolated_from_frozen_baseline() -> None:
    assert FROZEN_METHOD == "envsolve-pro-operation-contract"
    assert "run_envsolve_operation_episode.py" in inspect.getsource(
        EnvSolveProRunner.run
    )

    assert METHOD == "envsolve-pro-bootstrap-frontier-v2"
    assert METHOD_PROFILE["constraint_profile"] == (
        "bootstrap-contradiction-frontier-v2"
    )
    assert METHOD_PROFILE["operation_profile"] == "open-program"
    assert METHOD_PROFILE["base_environment_observation"] == "model-visible"
    assert issubclass(
        EnvSolveProBootstrapFrontierRunner,
        FrontierExperimentRunner,
    )
    assert EnvSolveProBootstrapFrontierRunner.episode_tool == (
        "run_envsolve_bootstrap_frontier_episode.py"
    )
