from __future__ import annotations

import shlex

from envsolve.runtime.docker import DockerEnvironmentHandle
from envsolve.runtime.goal_verifier import ExecutableGoalContractVerifier
from envsolve.solver import DeploymentCandidate
from envsolve_harness.codex import minimal_b_mcp
from envsolve_harness.codex.minimal_b_mcp import (
    MinimalBExecutableGoalVerifier,
)


_NAMESPACE_UNAWARE_PROVIDED_MODULE_SCAN = '''\
        elif child.is_dir() and (
            (child / "__init__.py").is_file()
            or any(item.suffix in {".py", ".pyi"} for item in child.iterdir())
        ):
            provided.add(child.name)
'''
_NAMESPACE_AWARE_PROVIDED_MODULE_SCAN = '''\
        elif child.is_dir() and child.name.isidentifier():
            contains_python = any(
                item.is_file()
                and not item.is_symlink()
                and item.suffix in {".py", ".pyi"}
                for item in child.rglob("*")
            )
            if contains_python:
                provided.add(child.name)
'''


def boundary_v2_local_distribution_audit() -> str:
    """Extend the frozen audit with PEP 420 namespace-package discovery."""
    source = minimal_b_mcp._LOCAL_DISTRIBUTION_AUDIT
    if _NAMESPACE_AWARE_PROVIDED_MODULE_SCAN in source:
        return source
    if source.count(_NAMESPACE_UNAWARE_PROVIDED_MODULE_SCAN) != 1:
        raise RuntimeError("cannot install boundary-v2 namespace-package audit")
    return source.replace(
        _NAMESPACE_UNAWARE_PROVIDED_MODULE_SCAN,
        _NAMESPACE_AWARE_PROVIDED_MODULE_SCAN,
        1,
    )


def install_boundary_v2_local_distribution_audit() -> None:
    minimal_b_mcp._LOCAL_DISTRIBUTION_AUDIT = (
        boundary_v2_local_distribution_audit()
    )


class NonInterferingExecutableGoalVerifier(ExecutableGoalContractVerifier):
    """Run the trusted goal without candidate-defined shell functions."""

    check_profile = "noninterfering-executable-goal-contract-v3"

    def _command(
        self,
        candidate: DeploymentCandidate,
        handle: DockerEnvironmentHandle,
        nonce: str,
    ) -> tuple[str, str, str]:
        command, completion_marker, report_begin = super()._command(
            candidate,
            handle,
            nonce,
        )
        legacy_goal = "\n".join(
            (
                "set +e",
                "(",
                "set -e",
                self.contract.program.rstrip(),
                ")",
                "ENVSOLVE_GOAL_EXIT_CODE=$?",
            )
        )
        trusted_goal = "\n".join(("set -e", self.contract.program.rstrip()))
        isolated_goal = "\n".join(
            (
                "set +e",
                (
                    "/usr/bin/env -u BASH_ENV -u ENV "
                    "/bin/bash --noprofile --norc -p -c "
                    f"{shlex.quote(trusted_goal)}"
                ),
                "ENVSOLVE_GOAL_EXIT_CODE=$?",
            )
        )
        if command.count(legacy_goal) != 1:
            raise RuntimeError("cannot isolate executable goal shell boundary")
        return (
            command.replace(legacy_goal, isolated_goal, 1),
            completion_marker,
            report_begin,
        )


class BoundaryV2MinimalBExecutableGoalVerifier(
    MinimalBExecutableGoalVerifier,
    NonInterferingExecutableGoalVerifier,
):
    """Keep Minimal B provenance checks and isolate the trusted goal shell."""

    check_profile = "minimal-b-executable-goal-contract-boundary-v2"
