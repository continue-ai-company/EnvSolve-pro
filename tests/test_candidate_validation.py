from __future__ import annotations

import unittest

from envsolve.solver import DeploymentCandidate
from envsolve_harness.scripts import TypedReplayCandidateValidator


class CompleteCandidateValidationTest(unittest.TestCase):
    def test_accepts_only_replayable_environment_mutations(self) -> None:
        validator = TypedReplayCandidateValidator()
        accepted = validator.validate(
            DeploymentCandidate(
                "candidate-1",
                "python -m pip install -e .\n",
                "Install the project",
            )
        )
        source_edit = validator.validate(
            DeploymentCandidate(
                "candidate-2",
                "sed -i 's/fail/pass/' package.py\n",
                "Modify source",
            )
        )
        observation = validator.validate(
            DeploymentCandidate("candidate-3", "ls -la\n", "Inspect files")
        )
        venv = validator.validate(
            DeploymentCandidate(
                "candidate-4",
                "python3 -m venv venv\nsource venv/bin/activate\n",
                "Create an isolated runtime",
            )
        )
        venv_executables = validator.validate(
            DeploymentCandidate(
                "candidate-5",
                (
                    "python3.10 -m venv .venv\n"
                    ".venv/bin/pip install --upgrade pip setuptools wheel\n"
                    ".venv/bin/python -m pip install -e .\n"
                    "source .venv/bin/activate\n"
                ),
                "Install through a bounded project virtual environment",
            )
        )
        unbound_venv = validator.validate(
            DeploymentCandidate(
                "candidate-6",
                (
                    "python3.10 -m venv .venv\n"
                    ".venv/bin/python -m pip install -e .\n"
                ),
                "Install without binding later verification",
            )
        )
        mismatched_activation = validator.validate(
            DeploymentCandidate(
                "candidate-7",
                "python -m venv .venv\nsource venv/bin/activate\n",
                "Activate another environment",
            )
        )
        activation_before_creation = validator.validate(
            DeploymentCandidate(
                "candidate-8",
                "source .venv/bin/activate\npython -m venv .venv\n",
                "Activate before creating the environment",
            )
        )
        cwd_mismatch = validator.validate(
            DeploymentCandidate(
                "candidate-9",
                (
                    "cd tools && python -m venv .venv\n"
                    "source ${PROJECT_ROOT}/.venv/bin/activate\n"
                ),
                "Create and activate different effective paths",
            )
        )
        cwd_activation = validator.validate(
            DeploymentCandidate(
                "candidate-10",
                (
                    "python -m venv .venv\n"
                    "cd tools && source .venv/bin/activate\n"
                ),
                "Activate a nested environment",
            )
        )
        pdm = validator.validate(
            DeploymentCandidate(
                "candidate-11",
                (
                    "python -m venv .venv\n"
                    "source .venv/bin/activate\n"
                    "python -m pip install pdm\n"
                    "pdm install -G :all\n"
                ),
                "Install a PDM project in the bound environment",
            )
        )

        self.assertTrue(accepted.accepted)
        self.assertEqual(
            accepted.normalized_script,
            "set -euo pipefail\npython -m pip install -e .\n",
        )
        self.assertFalse(source_edit.accepted)
        self.assertFalse(observation.accepted)
        self.assertTrue(venv.accepted)
        self.assertEqual(
            venv.normalized_script,
            "set -euo pipefail\npython3 -m venv venv\nsource venv/bin/activate\n",
        )
        self.assertTrue(venv_executables.accepted)
        self.assertEqual(
            venv_executables.details["action_count"],
            4,
        )
        self.assertFalse(unbound_venv.accepted)
        self.assertEqual(
            unbound_venv.reason,
            "created virtual environment .venv must be activated after creation",
        )
        self.assertFalse(mismatched_activation.accepted)
        self.assertFalse(activation_before_creation.accepted)
        self.assertFalse(cwd_mismatch.accepted)
        self.assertEqual(
            cwd_mismatch.reason,
            "virtual environment must be created at the project root",
        )
        self.assertFalse(cwd_activation.accepted)
        self.assertEqual(
            cwd_activation.reason,
            "virtual environment activation must resolve from the project root",
        )
        self.assertTrue(pdm.accepted)


if __name__ == "__main__":
    unittest.main()
