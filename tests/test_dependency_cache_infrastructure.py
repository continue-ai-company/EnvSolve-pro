from __future__ import annotations

import json
from pathlib import Path
import tempfile

import pytest

from experiments.tools.analyze_dependency_downloads import analyze_run_root
from experiments.tools.dependency_cache_attestation import build_attestation
from experiments.tools.dependency_cache_snapshot import (
    build_manifest,
    verify_manifest,
)


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
