from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

import pytest

from experiments.tools.analyze_dependency_downloads import analyze_run_root
from experiments.tools.dependency_cache_attestation import build_attestation
from experiments.tools.dependency_cache_episode import (
    finalize_episode,
    prepare_episode,
    summarize_service_logs,
)
from experiments.tools.dependency_cache_snapshot import (
    build_manifest,
    verify_manifest,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_cache_services_tolerate_slow_upstreams() -> None:
    devpi_dockerfile = (
        REPOSITORY_ROOT / "experiments/dependency_cache/devpi.Dockerfile"
    ).read_text(encoding="utf-8")
    apt_config = (
        REPOSITORY_ROOT / "experiments/dependency_cache/apt-cacher-ng.conf"
    ).read_text(encoding="utf-8")

    assert '"--request-timeout", "120"' in devpi_dockerfile
    assert "NetworkTimeout: 120" in apt_config
    assert "DlMaxRetries: 5" in apt_config


def test_cache_client_routes_only_ubuntu_archives_through_apt_proxy() -> None:
    client_dockerfile = (
        REPOSITORY_ROOT / "experiments/dependency_cache/client.Dockerfile"
    ).read_text(encoding="utf-8")

    assert "PIP_DEFAULT_TIMEOUT_SECONDS=180" in client_dockerfile
    assert "ENV PIP_DEFAULT_TIMEOUT=${PIP_DEFAULT_TIMEOUT_SECONDS}" in (
        client_dockerfile
    )
    assert 'Acquire::http::Proxy "DIRECT";' in client_dockerfile
    for host in (
        "ports.ubuntu.com",
        "archive.ubuntu.com",
        "security.ubuntu.com",
    ):
        assert f"Acquire::http::Proxy::{host}" in client_dockerfile
    assert 'Acquire::Queue-Mode "access";' in client_dockerfile
    assert 'Acquire::http::Pipeline-Depth "0";' in client_dockerfile
    assert 'Acquire::http::Timeout "120";' in client_dockerfile
    assert 'Acquire::Retries "5";' in client_dockerfile


def test_representative_cache_replay_result_is_evidence_bound() -> None:
    validation_root = REPOSITORY_ROOT / "experiments/validations"
    result = json.loads(
        (
            validation_root / "dependency_cache_uer_py_replay_v1_results.json"
        ).read_text(encoding="utf-8")
    )
    preregistration_path = (
        REPOSITORY_ROOT / result["preregistration"]["path"]
    )
    snapshot_path = (
        REPOSITORY_ROOT / result["cache_snapshot"]["manifest_path"]
    )
    raw_log_path = REPOSITORY_ROOT / result["evidence"]["raw_log_archive"]

    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    assert sha256(preregistration_path) == result["preregistration"]["sha256"]
    assert sha256(snapshot_path) == result["cache_snapshot"]["manifest_sha256"]
    assert sha256(raw_log_path) == result["evidence"][
        "raw_log_archive_sha256"
    ]
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["snapshot_id"] == result["cache_snapshot"]["snapshot_id"]
    assert snapshot["roots"]["pypi"]["total_file_bytes"] == result[
        "cache_snapshot"
    ]["total_file_bytes"]

    conditions = result["conditions"]
    assert {
        condition["resolved_torch_version"]
        for condition in conditions.values()
    } == {"2.13.0+cu130"}
    assert conditions["warm_shared_cache"]["wrapper_exit_code"] == 0
    assert conditions["warm_shared_cache"]["cache_remote_reads"] == 0
    assert conditions["warm_shared_cache"]["cache_wheel_gets"] == 35
    assert result["cache_snapshot"]["unchanged_after_offline_replay"] is True


def test_cache_snapshot_detects_content_and_symlink_changes() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        pypi = root / "pypi"
        apt = root / "apt"
        pypi.mkdir()
        apt.mkdir()
        wheel = pypi / "package.whl"
        wheel.write_bytes(b"wheel")
        (apt / "package.deb").write_bytes(b"deb")
        (pypi / "latest").symlink_to("package.whl")
        roots = {"pypi": pypi, "apt": apt}

        manifest = build_manifest(roots, "frozen")

        assert verify_manifest(manifest, roots) == []
        assert manifest["snapshot_id"]
        assert manifest["roots"]["pypi"]["entry_count"] == 2
        wheel.write_bytes(b"changed")
        errors = verify_manifest(manifest, roots)
        assert errors[0].startswith("snapshot_id mismatch")
        assert "cache root differs: pypi" in errors


def test_cache_snapshot_rejects_symlinks_outside_root() -> None:
    with tempfile.TemporaryDirectory() as directory:
        parent = Path(directory)
        cache_root = parent / "cache"
        cache_root.mkdir()
        outside = parent / "outside.whl"
        outside.write_bytes(b"outside")
        (cache_root / "escape").symlink_to(outside)

        with pytest.raises(ValueError, match="escapes its root"):
            build_manifest({"pypi": cache_root}, "frozen")


def test_download_analysis_is_an_explicit_lower_bound() -> None:
    with tempfile.TemporaryDirectory() as directory:
        run_root = Path(directory)
        generation = run_root / "run" / "case" / "generation"
        generation.mkdir(parents=True)
        (generation / "budget_ledger.json").write_text(
            json.dumps(
                {
                    "usage": {
                        "candidates": 2,
                        "commands": 2,
                        "environments": 2,
                        "requests_started": 3,
                    }
                }
            ),
            encoding="utf-8",
        )
        events = [
            {
                "event_type": "action_finished",
                "payload": {
                    "observation": {
                        "stdout": (
                            "Downloading one (1.5 MB)\n"
                            "Get:1 apt package [500 kB]"
                        ),
                        "stderr": "",
                    }
                },
            },
            {
                "event_type": "action_finished",
                "payload": {
                    "observation": {
                        "stdout": "three (0.1 GB) ...[truncated]...",
                        "stderr": (
                            "Looking in indexes: https://pypi.org/simple\n"
                            "Using cached metadata (4 kB)"
                        ),
                    }
                },
            },
        ]
        (generation / "episode.jsonl").write_text(
            "".join(json.dumps(event) + "\n" for event in events),
            encoding="utf-8",
        )

        result = analyze_run_root(run_root)

        assert result["episodes_with_ledgers"] == 1
        assert result["fresh_environments"] == 2
        assert result["matched_download_size_markers"] == 3
        assert result["logged_download_bytes_lower_bound"] == 102_000_000
        assert result["truncated_action_outputs"] == 1
        assert result["download_channels_lower_bound"]["pip"]["bytes"] == (
            1_500_000
        )
        assert result["download_channels_lower_bound"]["apt"]["bytes"] == (
            500_000
        )
        assert result["download_channels_lower_bound"]["other"]["bytes"] == (
            100_000_000
        )
        assert result["cached_artifact_markers"] == 1
        assert result["network_host_mentions"] == {"pypi.org": 1}


def _image(role: str, labels: dict[str, str]) -> dict[str, object]:
    prefix = "org.envsolve.dependency-cache."
    return {
        "input_ref": f"example/{role}:test",
        "image_id": f"sha256:{role}",
        "repo_digests": [],
        "os": "linux",
        "architecture": "arm64",
        "labels": {
            f"{prefix}role": role,
            **{f"{prefix}{name}": value for name, value in labels.items()},
        },
    }


def test_cache_attestation_binds_snapshot_images_and_endpoints() -> None:
    endpoints = {
        "pypi": "http://host.docker.internal:3141/root/pypi/+simple/",
        "apt": "http://host.docker.internal:3142",
    }
    manifest = {"mode": "frozen", "snapshot_id": "snapshot-1"}
    images = {
        "pypi-service": _image("pypi-service", {}),
        "apt-service": _image("apt-service", {}),
        "client": _image(
            "client",
            {
                "snapshot": "snapshot-1",
                "mode": "frozen-offline",
                "upstream-miss-policy": "deny",
                **endpoints,
            },
        ),
    }

    attestation = build_attestation(
        manifest=manifest,
        manifest_sha256="manifest-sha256",
        images=images,
        endpoints=endpoints,
        cache_mode="frozen-offline",
        upstream_miss_policy="deny",
    )

    assert attestation["cache_snapshot_id"] == "snapshot-1"
    assert attestation["attestation_id"]
    assert attestation["images"]["client"]["image_id"] == "sha256:client"


def test_cache_attestation_rejects_mismatched_client_snapshot() -> None:
    endpoints = {"pypi": "pypi-endpoint", "apt": "apt-endpoint"}
    images = {
        "pypi-service": _image("pypi-service", {}),
        "apt-service": _image("apt-service", {}),
        "client": _image(
            "client",
            {
                "snapshot": "wrong",
                "mode": "frozen-offline",
                "upstream-miss-policy": "deny",
                **endpoints,
            },
        ),
    }

    try:
        build_attestation(
            manifest={"mode": "frozen", "snapshot_id": "expected"},
            manifest_sha256="manifest-sha256",
            images=images,
            endpoints=endpoints,
            cache_mode="frozen-offline",
            upstream_miss_policy="deny",
        )
    except ValueError as error:
        assert "snapshot" in str(error)
    else:
        raise AssertionError("mismatched client snapshot was accepted")


def test_isolated_seed_attestation_requires_frozen_seed() -> None:
    endpoints = {
        "pypi": "http://host.docker.internal:3141/root/pypi/+simple/",
        "apt": "http://host.docker.internal:3142",
    }
    images = {
        "pypi-service": _image("pypi-service", {}),
        "apt-service": _image("apt-service", {}),
        "client": _image(
            "client",
            {
                "snapshot": "snapshot-1",
                "mode": "isolated-seeded",
                "upstream-miss-policy": "allow",
                **endpoints,
            },
        ),
    }

    attestation = build_attestation(
        manifest={"mode": "frozen", "snapshot_id": "snapshot-1"},
        manifest_sha256="manifest-sha256",
        images=images,
        endpoints=endpoints,
        cache_mode="isolated-seeded",
        upstream_miss_policy="allow",
    )

    assert attestation["cache_mode"] == "isolated-seeded"
    assert attestation["upstream_miss_policy"] == "allow"


def test_episode_cache_copy_isolated_and_audited() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        pypi = root / "seed" / "devpi"
        apt = root / "seed" / "apt"
        pypi.mkdir(parents=True)
        apt.mkdir()
        (pypi / "cached.whl").write_bytes(b"seed-wheel")
        (apt / "cached.deb").write_bytes(b"seed-deb")
        seed_roots = {"pypi": pypi, "apt": apt}
        manifest = build_manifest(seed_roots, "frozen")
        manifest_path = root / "seed-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

        lease = prepare_episode(
            manifest_path=manifest_path,
            seed_roots=seed_roots,
            episode_root=root / "episode",
            episode_id="case-a",
            bind_address="127.0.0.1",
            clone_strategy="copy",
        )
        runtime_pypi = Path(lease["runtime_seed_roots"]["pypi"])
        (runtime_pypi / "online-miss.whl").write_bytes(b"episode-only")

        closed = finalize_episode(
            lease_path=root / "episode" / "metadata" / "lease.json",
            services_stopped=True,
        )

        assert closed["state"] == "closed"
        assert closed["seed_integrity_verified"] is True
        assert closed["final_cache"]["changed_from_seed"] is True
        assert closed["final_cache"]["root_deltas"]["pypi"] == {
            "entry_count": 1,
            "total_file_bytes": len(b"episode-only"),
        }
        assert not (pypi / "online-miss.whl").exists()
        assert verify_manifest(manifest, seed_roots) == []
        assert lease["client"]["docker_run_args"] == [
            "--add-host=host.docker.internal:host-gateway"
        ]


def test_episode_cache_rejects_reusing_runtime_root() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        pypi = root / "seed"
        pypi.mkdir()
        (pypi / "cached.whl").write_bytes(b"seed-wheel")
        seed_roots = {"pypi": pypi}
        manifest = build_manifest(seed_roots, "frozen")
        manifest_path = root / "seed-manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        episode_root = root / "episode"

        prepare_episode(
            manifest_path=manifest_path,
            seed_roots=seed_roots,
            episode_root=episode_root,
            episode_id="case-a",
            bind_address="127.0.0.1",
            clone_strategy="copy",
        )

        with pytest.raises(ValueError, match="already exists"):
            prepare_episode(
                manifest_path=manifest_path,
                seed_roots=seed_roots,
                episode_root=episode_root,
                episode_id="case-b",
                bind_address="127.0.0.1",
                clone_strategy="copy",
            )


def test_episode_finalization_rejects_changed_manifest_file() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        pypi = root / "seed"
        pypi.mkdir()
        (pypi / "cached.whl").write_bytes(b"seed-wheel")
        seed_roots = {"pypi": pypi}
        manifest_path = root / "seed-manifest.json"
        manifest_path.write_text(
            json.dumps(build_manifest(seed_roots, "frozen")),
            encoding="utf-8",
        )
        episode_root = root / "episode"
        prepare_episode(
            manifest_path=manifest_path,
            seed_roots=seed_roots,
            episode_root=episode_root,
            episode_id="case-a",
            bind_address="127.0.0.1",
            clone_strategy="copy",
        )
        manifest_path.write_text("{}\n", encoding="utf-8")

        with pytest.raises(ValueError, match="manifest file changed"):
            finalize_episode(
                lease_path=episode_root / "metadata" / "lease.json",
                services_stopped=True,
            )


def test_episode_service_log_summary_counts_causal_cache_events() -> None:
    logs = "\n".join(
        [
            "GET /root/pypi/+simple/six/",
            "GET /root/pypi/+f/abc/six.whl",
            "GET /root/pypi/+simple/humanize/",
            "GET /root/pypi/+f/def/humanize.whl",
            "reading remote: URL('https://example.invalid/humanize.whl')",
            "GET /root/pypi/+f/def/humanize.whl",
            "getting data timed out after 120 seconds",
        ]
    )

    assert summarize_service_logs(logs) == {
        "pypi_remote_reads": 1,
        "pypi_project_gets": 2,
        "pypi_file_gets": 3,
        "upstream_timeouts": 1,
    }
