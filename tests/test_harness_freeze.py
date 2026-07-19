from __future__ import annotations

import unittest
from unittest import mock

from envsolve_harness.integrity.freeze import _verified_image_provenance


class HarnessFreezeImageIdentityTest(unittest.TestCase):
    @mock.patch("envsolve_harness.integrity.freeze.docker_image_provenance")
    def test_requires_immutable_image_identity(self, provenance) -> None:
        provenance.return_value = {
            "reference": "example/image:latest",
            "inspect_error": "Docker socket unavailable",
        }

        with self.assertRaisesRegex(RuntimeError, "Cannot freeze evaluation image"):
            _verified_image_provenance("example/image:latest")

    @mock.patch("envsolve_harness.integrity.freeze.docker_image_provenance")
    def test_accepts_image_id_with_repository_digest(self, provenance) -> None:
        expected = {
            "reference": "example/image:latest",
            "id": "sha256:" + "a" * 64,
            "repo_digests": ["example/image@sha256:" + "b" * 64],
        }
        provenance.return_value = expected

        self.assertEqual(
            _verified_image_provenance("example/image:latest"),
            expected,
        )


if __name__ == "__main__":
    unittest.main()
