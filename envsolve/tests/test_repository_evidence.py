from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from envsolve.runtime.policy import StructuredModelDeploymentPolicy
from envsolve.runtime.repository_evidence import RepositoryEvidenceIndex
from envsolve.state import EnvironmentState


class _UnusedModel:
    def invoke(self, messages):
        raise AssertionError("Repository evidence tests do not invoke the model")


def _finding(
    subject: str,
    file: str,
    *,
    zero_based_line: int | None = None,
    one_based_line: int | None = None,
) -> dict[str, object]:
    provenance: dict[str, object] = {"file": file}
    if zero_based_line is not None:
        provenance["range"] = {"start": {"line": zero_based_line}}
    if one_based_line is not None:
        provenance["line"] = one_based_line
    return {"subject": subject, "provenance": provenance}


def _state_with_findings(findings: list[dict[str, object]]) -> EnvironmentState:
    state = EnvironmentState(
        "case",
        case={"case_id": "case", "repository": "owner/repo", "revision": "abc"},
    )
    state.verifications.append(
        {
            "verification_id": "verification-1",
            "verifier": "goal",
            "passed": False,
            "details": {
                "candidate_id": "candidate-1",
                "verifier_details": {
                    "report_details": {
                        "goal_report": {
                            "status": "fail",
                            "findings": findings,
                        }
                    }
                },
            },
        }
    )
    return state


class RepositoryEvidenceIndexTests(unittest.TestCase):
    def test_routes_diagnostic_to_target_and_related_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            test_file = root / "extension_helpers/tests/test_setup_helpers.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text(
                "\n".join(
                    (
                        "def prepare_fixture(test_pkg):",
                        '    package = test_pkg / "helpers_test_package"',
                        "    package.mkdir()",
                        '    (package / "__init__.py").touch()',
                        "",
                        "def verify_fixture():",
                        "    import helpers_test_package",
                    )
                ),
                encoding="utf-8",
            )
            index = RepositoryEvidenceIndex(root)

            evidence = index.retrieve(
                [
                    _finding(
                        "helpers_test_package",
                        "/data/project/extension_helpers/tests/test_setup_helpers.py",
                        zero_based_line=6,
                    )
                ]
            )

            query = evidence["queries"][0]
            self.assertEqual(
                query["diagnostic_path"],
                "extension_helpers/tests/test_setup_helpers.py",
            )
            self.assertEqual(query["diagnostic_line"], 7)
            self.assertIn(
                "7:     import helpers_test_package",
                query["target_excerpt"]["text"],
            )
            related = "\n".join(
                occurrence["text"] for occurrence in query["related_occurrences"]
            )
            self.assertIn('test_pkg / "helpers_test_package"', related)
            self.assertIn("import helpers_test_package", related)

    def test_plain_line_number_remains_one_based(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            (root / "module.py").write_text(
                "first\nimport missing_name\nthird\n",
                encoding="utf-8",
            )

            evidence = RepositoryEvidenceIndex(root).retrieve(
                [_finding("missing_name", "module.py", one_based_line=2)]
            )

            self.assertEqual(evidence["queries"][0]["diagnostic_line"], 2)
            self.assertIn(
                "2: import missing_name",
                evidence["queries"][0]["target_excerpt"]["text"],
            )

    def test_does_not_resolve_path_outside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "repo"
            root.mkdir()
            outside = base / "private.py"
            outside.write_text("outside_secret = True\n", encoding="utf-8")
            (root / "public.py").write_text("public_value = True\n", encoding="utf-8")

            evidence = RepositoryEvidenceIndex(root).retrieve(
                [_finding("outside_secret", str(outside), one_based_line=1)]
            )

            query = evidence["queries"][0]
            self.assertIsNone(query["diagnostic_path"])
            self.assertIsNone(query["target_excerpt"])
            self.assertFalse(query["related_occurrences"])
            self.assertNotIn("outside_secret = True", json.dumps(evidence))

    def test_output_is_strictly_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            (root / "large.py").write_text(
                "\n".join(f"missing_name = {index}" for index in range(200)),
                encoding="utf-8",
            )

            evidence = RepositoryEvidenceIndex(root).retrieve(
                [_finding("missing_name", "large.py", one_based_line=100)],
                max_chars=256,
            )

            self.assertLessEqual(
                len(json.dumps(evidence, ensure_ascii=True, sort_keys=True)),
                256,
            )
            self.assertTrue(evidence["truncated"])

    def test_bounding_preserves_each_constraint_query(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            findings = []
            for index in range(3):
                subject = f"missing_name_{index}"
                path = root / f"module_{index}.py"
                path.write_text(
                    "\n".join(
                        f"{subject} = {line}  # {'context' * 10}"
                        for line in range(20)
                    ),
                    encoding="utf-8",
                )
                findings.append(
                    _finding(subject, path.name, one_based_line=10)
                )

            evidence = RepositoryEvidenceIndex(root).retrieve(
                findings,
                max_chars=1_500,
            )

            self.assertEqual(
                [query["subject"] for query in evidence["queries"]],
                ["missing_name_0", "missing_name_1", "missing_name_2"],
            )
            self.assertLessEqual(
                len(json.dumps(evidence, ensure_ascii=True, sort_keys=True)),
                1_500,
            )

    def test_routes_distinct_subjects_before_duplicate_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            (root / "imports.py").write_text(
                "\n".join(
                    (
                        "import pytest",
                        "import pytest",
                        "import pytest",
                        "import nonebug",
                        "import tomli",
                    )
                ),
                encoding="utf-8",
            )

            evidence = RepositoryEvidenceIndex(root).retrieve(
                [
                    _finding("pytest", "imports.py", one_based_line=1),
                    _finding("pytest", "imports.py", one_based_line=2),
                    _finding("pytest", "imports.py", one_based_line=3),
                    _finding("nonebug", "imports.py", one_based_line=4),
                    _finding("tomli", "imports.py", one_based_line=5),
                ],
                max_queries=2,
            )

            self.assertEqual(
                [query["subject"] for query in evidence["queries"]],
                ["pytest", "nonebug"],
            )
            self.assertEqual(evidence["input_finding_count"], 5)
            self.assertEqual(evidence["distinct_subject_count"], 3)
            self.assertEqual(evidence["included_query_count"], 2)
            self.assertEqual(evidence["omitted_query_count"], 1)


class RepositoryEvidencePolicyTests(unittest.TestCase):
    def test_constraint_routed_profile_projects_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "test_fixture.py").write_text(
                "def make_fixture(path):\n"
                '    (path / "generated_module").mkdir()\n'
                "\n"
                "import generated_module\n",
                encoding="utf-8",
            )
            state = _state_with_findings(
                [
                    _finding(
                        "generated_module",
                        "/data/project/test_fixture.py",
                        zero_based_line=3,
                    )
                ]
            )

            projection = StructuredModelDeploymentPolicy(
                _UnusedModel(),
                {"files": ["test_fixture.py"]},
                repository_evidence_profile="constraint-routed",
                repository_root=root,
                operation_profile="free-form",
            )._state_projection(state)

            self.assertIn("repository_evidence", projection)
            rendered = json.dumps(projection["repository_evidence"])
            self.assertIn("generated_module", rendered)
            self.assertIn("mkdir", rendered)

    def test_disabled_profile_does_not_project_evidence(self) -> None:
        state = _state_with_findings(
            [_finding("missing_name", "module.py", one_based_line=1)]
        )

        projection = StructuredModelDeploymentPolicy(
            _UnusedModel(),
            {"files": ["module.py"]},
            repository_evidence_profile="disabled",
            operation_profile="free-form",
        )._state_projection(state)

        self.assertNotIn("repository_evidence", projection)

    def test_constraint_routed_profile_requires_repository_root(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires a repository root"):
            StructuredModelDeploymentPolicy(
                _UnusedModel(),
                {"files": []},
                repository_evidence_profile="constraint-routed",
            )

    def test_candidate_records_exact_model_input_projection(self) -> None:
        class _ResponseModel:
            def invoke(self, messages):
                return type(
                    "Response",
                    (),
                    {
                        "content": json.dumps(
                            {
                                "script": "python -m pip install -e .",
                                "rationale": "Install the project",
                            }
                        )
                    },
                )()

        state = EnvironmentState(
            "case",
            case={"case_id": "case", "repository": "owner/repo", "revision": "abc"},
        )
        candidate = StructuredModelDeploymentPolicy(
            _ResponseModel(),
            {"files": ["pyproject.toml"]},
            operation_profile="free-form",
        ).propose(state)

        projection = candidate.metadata["model_input_projection"]
        encoded = json.dumps(
            projection,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        self.assertEqual(
            candidate.metadata["model_input_projection_schema"],
            "envsolve-model-input-projection-v1",
        )
        self.assertEqual(
            candidate.metadata["model_input_projection_chars"],
            len(encoded),
        )
        self.assertEqual(
            candidate.metadata["model_input_projection_sha256"],
            hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
