from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from envsolve.runtime import (
    DockerFreshEnvironmentProvider,
    PythonDeploymentVerifier,
    WorkspacePrecondition,
)
from envsolve.solver import (
    CandidateAssessment,
    CandidateValidation,
    CounterexampleEvidence,
    CounterexampleGuidedDeploymentLoop,
    DeploymentCandidate,
    SolverStateSession,
)
from envsolve_harness.integrity.repository import inspect_repository


@unittest.skipUnless(
    os.environ.get("ENVSOLVE_DOCKER_TEST") == "1",
    "set ENVSOLVE_DOCKER_TEST=1 to run the real Docker boundary test",
)
class EnvSolveDockerIntegrationTest(unittest.TestCase):
    def test_persistent_construction_reuse_and_clean_replay_are_distinct(
        self,
    ) -> None:
        class Policy:
            def __init__(self, script: str) -> None:
                self.candidates = [
                    DeploymentCandidate("candidate-1", script, "initial setup"),
                    DeploymentCandidate("candidate-2", script, "cumulative repair"),
                ]

            def propose(self, _state):
                return self.candidates.pop(0)

        class Validator:
            def validate(self, candidate):
                return CandidateValidation(
                    True,
                    "docker-persistent-integration",
                    candidate.script,
                )

        class Budget:
            def reserve_candidate(self, _candidate_id):
                return None

            def reserve_environment(self, _candidate_id):
                return None

            def reserve_command(self, _candidate_id):
                return None

        class FirstFailureVerifier:
            def __init__(self, delegate) -> None:
                self.delegate = delegate
                self.calls = 0

            def verify(self, candidate, environment):
                self.calls += 1
                result = self.delegate.verify(candidate, environment)
                if self.calls != 1:
                    return result
                return replace(
                    result,
                    passed=False,
                    summary="Synthetic residual constraint after completed setup",
                    counterexamples=(
                        CounterexampleEvidence(
                            "module-requirement",
                            {"name": "synthetic.remaining", "present": True},
                        ),
                        CounterexampleEvidence(
                            "module-observation",
                            {"name": "synthetic.remaining", "present": False},
                        ),
                    ),
                    candidate_assessment=CandidateAssessment(
                        True,
                        1,
                        0,
                        0,
                        "complete setup with one synthetic residual",
                    ),
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "setup.py").write_text(
                "from setuptools import setup\n"
                "setup(name='envsolve-persistent-smoke', version='0.0.1')\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "init", "-q"], cwd=source, check=True)
            subprocess.run(
                ["git", "config", "user.email", "envsolve@example.test"],
                cwd=source,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "EnvSolve Test"],
                cwd=source,
                check=True,
            )
            subprocess.run(["git", "add", "setup.py"], cwd=source, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=source, check=True)
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=source,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            provider = DockerFreshEnvironmentProvider(
                source_repository=source,
                worktrees_root=root / "worktrees",
                repository="envsolve/persistent-smoke",
                revision=revision,
                image="ghcr.io/jetbrains-research/envbench-python:latest",
            )
            script = (
                "if [ -f /tmp/envsolve-persistent-marker ]; then\n"
                "  echo ENVSOLVE_STATE=REUSED\n"
                "else\n"
                "  echo ENVSOLVE_STATE=FRESH\n"
                "fi\n"
                "touch /tmp/envsolve-persistent-marker\n"
                "python -m pip install --no-deps --no-build-isolation -e .\n"
            )
            verifier = FirstFailureVerifier(
                PythonDeploymentVerifier(
                    command_timeout=180,
                    collect_tests=False,
                    effect_auditor=lambda worktree: inspect_repository(
                        worktree,
                        revision,
                    ),
                )
            )
            session = SolverStateSession(
                root / "episode.jsonl",
                root / "episode_snapshot.json",
                {
                    "case_id": "envsolve-persistent-smoke",
                    "repository": "envsolve/persistent-smoke",
                    "revision": revision,
                },
            )
            result = CounterexampleGuidedDeploymentLoop(
                session,
                max_candidates=2,
                candidate_validator=Validator(),
                budget=Budget(),
                environment_strategy="postcondition-persistent",
            ).run(
                Policy(script),
                provider,
                verifier,
            )

            state = session.reconstruct()
            self.assertIn(
                "candidate-2",
                state.actions,
                {
                    "result": result.to_dict(),
                    "failures": state.failures,
                    "verifications": state.verifications,
                },
            )
            construction = state.actions["candidate-2"]["observation"]["stdout"]
            clean = state.actions["candidate-2-clean-replay"]["observation"]["stdout"]

            self.assertEqual(result.goal_status, "satisfied")
            self.assertIn("ENVSOLVE_STATE=REUSED", construction)
            self.assertIn("ENVSOLVE_STATE=FRESH", clean)
            self.assertNotEqual(
                state.verifications[-2]["details"]["environment_receipt"][
                    "environment_id"
                ],
                state.verifications[-1]["details"]["environment_receipt"][
                    "environment_id"
                ],
            )
            self.assertFalse(any((root / "worktrees").iterdir()))

    def test_clean_checkout_candidate_verification_and_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "setup.py").write_text(
                "from setuptools import setup\nsetup(name='envsolve-smoke', version='0.0.1')\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "init", "-q"], cwd=source, check=True)
            subprocess.run(
                ["git", "config", "user.email", "envsolve@example.test"],
                cwd=source,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "EnvSolve Test"],
                cwd=source,
                check=True,
            )
            subprocess.run(["git", "add", "setup.py"], cwd=source, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=source, check=True)
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=source,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            provider = DockerFreshEnvironmentProvider(
                source_repository=source,
                worktrees_root=root / "worktrees",
                repository="envsolve/smoke",
                revision=revision,
                image="ghcr.io/jetbrains-research/envbench-python:latest",
                workspace_preconditions=(
                    WorkspacePrecondition(
                        "build_output",
                        producer="docker-integration-fixture",
                    ),
                ),
            )
            candidate = DeploymentCandidate(
                "candidate-1",
                (
                    "if ! python -c 'import envsolve_smoke' 2>/dev/null; then\n"
                    "  python -m pip install --no-deps --no-build-isolation -e .\n"
                    "fi\n"
                ),
                "Install the synthetic project",
                metadata={
                    "candidate_validation": {
                        "policy_id": "open-candidate-program-v1",
                        "details": {},
                    }
                },
            )
            base_runtime = provider.observe_base_runtime()
            environment = provider.provision(candidate)
            try:
                result = PythonDeploymentVerifier(
                    command_timeout=180,
                    collect_tests=False,
                    effect_auditor=lambda worktree: inspect_repository(
                        worktree,
                        revision,
                        required_preconditions=provider.workspace_preconditions,
                    ),
                ).verify(candidate, environment)
            finally:
                provider.release(environment)

            self.assertTrue(base_runtime.python_version)
            self.assertEqual(
                base_runtime.image_digest,
                environment.receipt.image_digest,
            )
            self.assertTrue(result.passed, result.bootstrap.stderr)
            self.assertTrue(
                result.details["report_details"]["repository_effect_audit"]["valid"]
            )
            self.assertFalse(environment.handle.worktree.exists())

            source_edit = DeploymentCandidate(
                "candidate-2",
                "printf '\\n# modified\\n' >> setup.py\n",
                "Attempt to change tracked project state",
                metadata=candidate.metadata,
            )
            edited_environment = provider.provision(source_edit)
            try:
                edited = PythonDeploymentVerifier(
                    command_timeout=180,
                    collect_tests=False,
                    effect_auditor=lambda worktree: inspect_repository(
                        worktree,
                        revision,
                        required_preconditions=provider.workspace_preconditions,
                    ),
                ).verify(source_edit, edited_environment)
            finally:
                provider.release(edited_environment)
            self.assertFalse(edited.passed)
            self.assertIn("effect boundaries", edited.summary)


if __name__ == "__main__":
    unittest.main()
