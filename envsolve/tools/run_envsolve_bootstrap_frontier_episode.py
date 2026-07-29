#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


# ruff: noqa: E402 - workspace path bootstrapping must precede local imports.

ROOT = Path(__file__).resolve().parents[2]
ENVBENCH = ROOT / "EnvBench"
for path in (ROOT, ENVBENCH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from envsolve.runtime.bootstrap_frontier_policy import (
    BootstrapFrontierDeploymentPolicy,
)
from envsolve.runtime.docker import DockerFreshEnvironmentProvider
from envsolve.tools import run_envsolve_episode


_BASE_RUNTIME_OBSERVATION: dict[str, str] | None = None


class _ObservedBootstrapEnvironmentProvider(DockerFreshEnvironmentProvider):
    def observe_base_runtime(self):
        global _BASE_RUNTIME_OBSERVATION
        observation = super().observe_base_runtime()
        _BASE_RUNTIME_OBSERVATION = observation.to_dict()
        return observation


class _ObservedBootstrapFrontierPolicy(BootstrapFrontierDeploymentPolicy):
    def __init__(
        self,
        model: Any,
        repository_profile: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        if _BASE_RUNTIME_OBSERVATION is None:
            raise RuntimeError(
                "Bootstrap-frontier policy requires a base runtime observation"
            )
        super().__init__(
            model,
            {
                **repository_profile,
                "base_environment_observation": _BASE_RUNTIME_OBSERVATION,
            },
            **kwargs,
        )


def main() -> int:
    run_envsolve_episode.DockerFreshEnvironmentProvider = (
        _ObservedBootstrapEnvironmentProvider
    )
    run_envsolve_episode.StructuredModelDeploymentPolicy = (
        _ObservedBootstrapFrontierPolicy
    )
    return run_envsolve_episode.main()


if __name__ == "__main__":
    raise SystemExit(main())
