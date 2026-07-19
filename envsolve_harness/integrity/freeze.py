from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable, Mapping

from envsolve_harness.adapters.registry import registered_benchmark_adapters
from envsolve_harness.core.config import load_harness_config
from envsolve_harness.core.models import HarnessConfig
from envsolve_harness.core.protocol import load_protocol
from envsolve_harness.runners.registry import registered_solver_runners
from envsolve_harness.scripts.replay_actions import REPLAY_IR_POLICY
from envsolve_harness.storage.manifest import MANIFEST_SCHEMA_VERSION
from envsolve_harness.utils.provenance import (
    docker_image_provenance,
    git_provenance,
    sha256_file,
)


FREEZE_SCHEMA_VERSION = "1.0.0"
FREEZE_ID = "envsolve-harness-v23"
FREEZE_MANIFEST_PATH = Path("experiments/protocols/harness_freeze_v23.json")
SUPERSEDED_FREEZE_ID = "envsolve-harness-v22"
SUPERSEDED_FREEZE_PATH = Path("experiments/protocols/harness_freeze_v22.json")
CONFIG_PATH = Path("experiments/configs/local_mac.json")
PROTOCOL_PATH = Path("experiments/protocols/envbench_python_official_v1.json")
TYPED_IR_FREEZE_PATH = Path(
    "experiments/protocols/typed_replay_ir_v7_freeze.json"
)
DATASET_PATHS = (
    Path("experiments/cases/split_manifest.json"),
    Path("experiments/cases/envbench_python_329.jsonl"),
    Path("experiments/cases/dev5.jsonl"),
    Path("experiments/cases/dev_extension3.jsonl"),
    Path("experiments/cases/canary20.jsonl"),
    Path("experiments/cases/train_rest204.jsonl"),
    Path("experiments/cases/train_untouched201.jsonl"),
    Path("experiments/cases/dev_v3_qualification5.jsonl"),
    Path("experiments/cases/train_untouched_after_v3_qualification196.jsonl"),
    Path("experiments/cases/official_test100.jsonl"),
    Path("experiments/cases/smoke.jsonl"),
    Path("experiments/cases/upstream/python_baseline_failure_all.jsonl"),
    Path("experiments/cases/upstream/python_baseline_failure_test.jsonl"),
    Path("experiments/validations/p6_v3_unseen_dev5_preregistration.json"),
    Path("experiments/validations/p6_v3_unseen_dev5_selection.json"),
    Path("experiments/validations/p6_v3_unseen_dev5_schedule.json"),
    Path("experiments/validations/p6_v3_q1_position1_harness_diagnostic.json"),
    Path("experiments/validations/p6_v3_q1_position2_infrastructure_diagnostic.json"),
    Path("experiments/validations/p6_v3_q1_position2_retry1_diagnostic.json"),
    Path("experiments/validations/p6_v3_q1_position3_evaluator_infrastructure_diagnostic.json"),
    Path("experiments/validations/p6_v3_q1_position4_result_and_budget_diagnostic.json"),
    Path("experiments/cases/dev_operation_qualification_v4_5.jsonl"),
    Path("experiments/cases/dev_operation_qualification_v5_5.jsonl"),
    Path("experiments/cases/train_untouched_after_operation_qualification_v5_171.jsonl"),
    Path("experiments/cases/dev_operation_qualification_v6_5.jsonl"),
    Path("experiments/cases/train_untouched_after_operation_qualification_v6_166.jsonl"),
    Path("experiments/validations/p6_operation_qualification_v4_preregistration.json"),
    Path("experiments/validations/p6_operation_qualification_v4_selection.json"),
    Path("experiments/validations/p6_operation_qualification_v4_schedule.json"),
    Path("experiments/validations/p6_operation_q4_results.json"),
    Path("experiments/validations/p6_operation_qualification_v5_preregistration.json"),
    Path("experiments/validations/p6_operation_qualification_v5_selection.json"),
    Path("experiments/validations/p6_operation_qualification_v5_schedule.json"),
    Path("experiments/validations/p6_operation_qualification_v6_preregistration.json"),
    Path("experiments/validations/p6_operation_qualification_v6_selection.json"),
    Path("experiments/validations/p6_operation_qualification_v6_schedule.json"),
    Path("experiments/validations/p6_operation_q6_results.json"),
    Path("experiments/cases/dev_operation_qualification_v7_5.jsonl"),
    Path("experiments/cases/train_untouched_after_operation_qualification_v7_161.jsonl"),
    Path("experiments/validations/p6_operation_qualification_v7_preregistration.json"),
    Path("experiments/validations/p6_operation_qualification_v7_selection.json"),
    Path("experiments/validations/p6_operation_qualification_v7_schedule.json"),
    Path("experiments/validations/p6_operation_q7_audit.json"),
    Path("experiments/validations/p6_operation_q7_results.json"),
    Path("experiments/protocols/p6_operation_qualification_freeze_v7.json"),
)
OFFICIAL_CHANNEL_CONTRACT = {
    "scoring": True,
    "recomputed_by_audit": True,
}
DIAGNOSTIC_CHANNEL_CONTRACT = {
    "scoring": False,
    "verifiers": [
        "envbench-bootstrap-diagnostic",
        "envbench-pyright-diagnostic",
    ],
}
DEVELOPMENT_DISCLOSURE = {
    "development_only_splits": [
        "dev-5",
        "dev-extension-3",
        "dev-v3-qualification-5",
        "dev-operation-qualification-q1-q7",
    ],
    "untouched_confirmatory_splits": ["canary-20", "official-test-100"],
    "case_specific_rules": False,
}


@dataclass(frozen=True)
class FreezeVerification:
    valid: bool
    errors: tuple[str, ...]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _relative_file_map(root: Path, files: Iterable[Path]) -> dict[str, str]:
    return {
        str(path.resolve().relative_to(root.resolve())): sha256_file(path)
        for path in sorted({path.resolve() for path in files})
        if path.is_file() and "__pycache__" not in path.parts
    }


def _glob_files(root: Path, patterns: Iterable[str]) -> list[Path]:
    return [path for pattern in patterns for path in root.glob(pattern) if path.is_file()]


def harness_source_files(root: Path) -> dict[str, str]:
    files = _glob_files(
        root,
        (
            "envsolve_harness/**/*.py",
            "envsolve/state/**/*.py",
            "envsolve/solver/**/*.py",
            "envsolve/runtime/**/*.py",
            "envsolve/constraints/**/*.py",
            "envsolve/verification/**/*.py",
            "envsolve/integrations/envbench_findings.py",
            "envsolve/v0/**/*.py",
            "envsolve/tools/run_v0_inference.py",
            "envsolve/tools/run_envsolve_episode.py",
            "experiments/*.py",
            "experiments/tools/*.py",
            "experiments/scripts/**/*.sh",
            "tests/*.py",
            "envsolve/tests/**/*.py",
            "tests/fixtures/*.json",
            "research/P6_TWO_LAYER_IMPORT_OBLIGATIONS_V1.md",
            "research/P6_TWO_LAYER_IMPORT_OBLIGATIONS_V1_ZH.md",
            "research/P6_V3_UNSEEN_DEV5_QUALIFICATION_V1.md",
            "research/P6_V3_UNSEEN_DEV5_QUALIFICATION_V1_ZH.md",
        ),
    )
    excluded = {(root / FREEZE_MANIFEST_PATH).resolve()}
    return _relative_file_map(root, (path for path in files if path.resolve() not in excluded))


def _git_worktree_map(root: Path) -> dict[str, str]:
    process = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"Cannot enumerate Git worktree {root}: {detail}")
    snapshot: dict[str, str] = {}
    for raw_path in process.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = raw_path.decode("utf-8", errors="surrogateescape")
        path = root / relative
        if path.is_symlink():
            snapshot[relative] = f"symlink:{path.readlink()}"
        elif path.is_file():
            snapshot[relative] = f"sha256:{sha256_file(path)}"
        else:
            snapshot[relative] = "missing"
    return dict(sorted(snapshot.items()))


def _envbench_files(root: Path) -> dict[str, str]:
    return _git_worktree_map(root)


def _repo2run_files(root: Path) -> dict[str, str]:
    return _git_worktree_map(root)


def _aggregate_hash(files: dict[str, str]) -> str:
    payload = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return _sha256_bytes(payload)


def _component(root: Path, files: dict[str, str]) -> dict[str, object]:
    return {
        "root": str(root.resolve()),
        "git": git_provenance(root),
        "source_sha256": _aggregate_hash(files),
        "files": files,
    }


def _pricing_snapshot(config: HarnessConfig) -> dict[str, dict[str, Any]]:
    return {
        model: asdict(pricing)
        for model, pricing in sorted(config.model_pricing.items())
    }


def _registry_snapshot() -> dict[str, list[str]]:
    return {
        "benchmark_adapters": list(registered_benchmark_adapters()),
        "solver_runners": list(registered_solver_runners()),
    }


def build_harness_freeze(workspace_root: Path, created_at: str) -> dict[str, object]:
    root = workspace_root.resolve()
    config = load_harness_config(root / CONFIG_PATH, root)
    protocol = load_protocol(root / PROTOCOL_PATH)
    benchmark = config.benchmark(protocol.benchmark)
    envbench_files = _envbench_files(benchmark.root)
    repo2run_root = config.solver_root("repo2run")
    repo2run_files = _repo2run_files(repo2run_root)
    source_files = harness_source_files(root)
    typed_ir_freeze = json.loads((root / TYPED_IR_FREEZE_PATH).read_text())
    dataset_files = _relative_file_map(root, (root / path for path in DATASET_PATHS))
    image = str(benchmark.settings["image"])
    return {
        "schema_version": FREEZE_SCHEMA_VERSION,
        "freeze_id": FREEZE_ID,
        "created_at": created_at,
        "supersedes": {
            "freeze_id": SUPERSEDED_FREEZE_ID,
            "path": str(SUPERSEDED_FREEZE_PATH),
            "sha256": sha256_file(root / SUPERSEDED_FREEZE_PATH),
            "reason": "After Q7 exposed runtime-state regression, freeze fresh base-runtime observation, conditional requires-python admission, hard action-result constraints, cumulative operation preservation, and failed-prefix feasibility before any new development case.",
        },
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "harness_source": {
            "source_sha256": _aggregate_hash(source_files),
            "files": source_files,
        },
        "configuration": {
            "path": str(CONFIG_PATH),
            "sha256": sha256_file(root / CONFIG_PATH),
            "resource_budget": config.resource_budget(),
            "model_pricing": _pricing_snapshot(config),
        },
        "protocol": {
            "path": str(PROTOCOL_PATH),
            "sha256": sha256_file(root / PROTOCOL_PATH),
            "value": protocol.to_dict(),
            "official_channel": OFFICIAL_CHANNEL_CONTRACT,
            "diagnostic_channel": DIAGNOSTIC_CHANNEL_CONTRACT,
        },
        "typed_replay_ir": {
            "policy_id": REPLAY_IR_POLICY,
            "freeze_manifest": str(TYPED_IR_FREEZE_PATH),
            "freeze_manifest_sha256": sha256_file(root / TYPED_IR_FREEZE_PATH),
            "freeze": typed_ir_freeze,
        },
        "datasets": {
            "source_sha256": _aggregate_hash(dataset_files),
            "files": dataset_files,
        },
        "registries": _registry_snapshot(),
        "external_components": {
            "envbench": _component(benchmark.root, envbench_files),
            "repo2run": _component(repo2run_root, repo2run_files),
            "evaluation_image": docker_image_provenance(image),
        },
        "development_disclosure": DEVELOPMENT_DISCLOSURE,
    }


def _verify_file_map(root: Path, expected: dict[str, str], label: str) -> list[str]:
    errors: list[str] = []
    for relative, expected_hash in expected.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"{label}: missing file {relative}")
        elif sha256_file(path) != expected_hash:
            errors.append(f"{label}: hash mismatch for {relative}")
    return errors


def _mapping(value: object, label: str, errors: list[str]) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    errors.append(f"{label} must be an object")
    return {}


def _string_map(
    value: object,
    label: str,
    errors: list[str],
) -> dict[str, str]:
    mapping = _mapping(value, label, errors)
    if not all(isinstance(key, str) and isinstance(item, str) for key, item in mapping.items()):
        errors.append(f"{label} must map paths to SHA256 strings")
        return {}
    return dict(mapping)


def verify_harness_freeze(
    workspace_root: Path,
    freeze: dict[str, object],
) -> FreezeVerification:
    root = workspace_root.resolve()
    errors: list[str] = []
    if freeze.get("freeze_id") != FREEZE_ID:
        errors.append("freeze identifier mismatch")
    if freeze.get("schema_version") != FREEZE_SCHEMA_VERSION:
        errors.append("freeze schema version mismatch")
    if freeze.get("manifest_schema_version") != MANIFEST_SCHEMA_VERSION:
        errors.append("artifact manifest schema version mismatch")
    supersedes = _mapping(freeze.get("supersedes"), "supersedes", errors)
    if supersedes.get("freeze_id") != SUPERSEDED_FREEZE_ID:
        errors.append("superseded freeze identifier mismatch")
    if supersedes.get("path") != str(SUPERSEDED_FREEZE_PATH):
        errors.append("superseded freeze path mismatch")
    superseded_path = root / SUPERSEDED_FREEZE_PATH
    if (
        not superseded_path.is_file()
        or supersedes.get("sha256") != sha256_file(superseded_path)
    ):
        errors.append("superseded freeze hash mismatch")

    harness_source = _mapping(freeze.get("harness_source"), "harness_source", errors)
    expected_source = _string_map(
        harness_source.get("files"),
        "harness_source.files",
        errors,
    )
    current_source = harness_source_files(root)
    if current_source != expected_source:
        errors.append("harness source file set or content changed")
    errors.extend(_verify_file_map(root, expected_source, "harness source"))
    if harness_source.get("source_sha256") != _aggregate_hash(current_source):
        errors.append("harness source aggregate hash mismatch")

    dataset_record = _mapping(freeze.get("datasets"), "datasets", errors)
    expected_datasets = _string_map(dataset_record.get("files"), "datasets.files", errors)
    current_datasets = _relative_file_map(root, (root / path for path in DATASET_PATHS))
    if current_datasets != expected_datasets:
        errors.append("dataset file set or content changed")
    errors.extend(_verify_file_map(root, expected_datasets, "dataset"))
    if dataset_record.get("source_sha256") != _aggregate_hash(current_datasets):
        errors.append("dataset aggregate hash mismatch")

    configuration = _mapping(freeze.get("configuration"), "configuration", errors)
    protocol_record = _mapping(freeze.get("protocol"), "protocol", errors)
    typed_ir = _mapping(freeze.get("typed_replay_ir"), "typed_replay_ir", errors)
    expected_records = (
        (configuration, CONFIG_PATH, "configuration"),
        (protocol_record, PROTOCOL_PATH, "protocol"),
    )
    for record, expected_path, label in expected_records:
        if record.get("path") != str(expected_path):
            errors.append(f"{label} path mismatch")
        path = root / expected_path
        if not path.is_file() or record.get("sha256") != sha256_file(path):
            errors.append(f"{label} hash mismatch")

    config: HarnessConfig = load_harness_config(root / CONFIG_PATH, root)
    protocol = load_protocol(root / PROTOCOL_PATH)
    if config.resource_budget() != configuration.get("resource_budget"):
        errors.append("resource budget changed")
    if _pricing_snapshot(config) != configuration.get("model_pricing"):
        errors.append("model pricing changed")
    if protocol.to_dict() != protocol_record.get("value"):
        errors.append("protocol value changed")
    if protocol_record.get("official_channel") != OFFICIAL_CHANNEL_CONTRACT:
        errors.append("official channel contract changed")
    if protocol_record.get("diagnostic_channel") != DIAGNOSTIC_CHANNEL_CONTRACT:
        errors.append("diagnostic channel contract changed")

    if typed_ir.get("policy_id") != REPLAY_IR_POLICY:
        errors.append("typed replay IR policy changed")
    if typed_ir.get("freeze_manifest") != str(TYPED_IR_FREEZE_PATH):
        errors.append("typed replay IR freeze path mismatch")
    typed_path = root / TYPED_IR_FREEZE_PATH
    if not typed_path.is_file():
        errors.append("typed replay IR freeze is missing")
    else:
        if typed_ir.get("freeze_manifest_sha256") != sha256_file(typed_path):
            errors.append("typed replay IR freeze hash mismatch")
        current_typed_freeze = json.loads(typed_path.read_text(encoding="utf-8"))
        if typed_ir.get("freeze") != current_typed_freeze:
            errors.append("typed replay IR nested freeze changed")
        nested_files = _string_map(
            current_typed_freeze.get("files"),
            "typed_replay_ir.freeze.files",
            errors,
        )
        errors.extend(_verify_file_map(root, nested_files, "typed replay IR"))

    registries = _mapping(freeze.get("registries"), "registries", errors)
    if registries != _registry_snapshot():
        errors.append("runner or adapter registry changed")
    if freeze.get("development_disclosure") != DEVELOPMENT_DISCLOSURE:
        errors.append("development disclosure changed")

    components = _mapping(
        freeze.get("external_components"),
        "external_components",
        errors,
    )
    component_specs = {
        "envbench": (
            config.benchmark("envbench").root,
            _envbench_files(config.benchmark("envbench").root),
        ),
        "repo2run": (
            config.solver_root("repo2run"),
            _repo2run_files(config.solver_root("repo2run")),
        ),
    }
    for name, (component_root, current_files) in component_specs.items():
        expected_component = _mapping(components.get(name), name, errors)
        expected_files = _string_map(
            expected_component.get("files"),
            f"{name}.files",
            errors,
        )
        if current_files != expected_files:
            errors.append(f"{name} source file set or content changed")
        if expected_component.get("source_sha256") != _aggregate_hash(current_files):
            errors.append(f"{name} source aggregate hash mismatch")
        expected_git = _mapping(expected_component.get("git"), f"{name}.git", errors)
        current_git = git_provenance(component_root)
        for field in ("revision", "dirty", "status"):
            if current_git[field] != expected_git.get(field):
                errors.append(f"{name} Git {field} changed")

    image_record = _mapping(
        components.get("evaluation_image"),
        "evaluation_image",
        errors,
    )
    image_reference = image_record.get("reference")
    expected_image_reference = str(config.benchmark(protocol.benchmark).settings["image"])
    if image_reference != expected_image_reference:
        errors.append("evaluation image reference changed")
    current_image = docker_image_provenance(str(image_reference))
    if current_image != image_record:
        errors.append("evaluation image identity changed")
    return FreezeVerification(not errors, tuple(errors))
