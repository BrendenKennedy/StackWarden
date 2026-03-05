"""Manifest save/load and repro fingerprint distinctness tests."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from stackwarden.domain.manifest import ResolvedManifest, save_manifest, load_manifest


@pytest.fixture
def tmp_artifacts(tmp_path):
    with patch("stackwarden.paths.get_artifacts_root", return_value=tmp_path):
        yield tmp_path


class TestManifestSaveLoad:
    def test_round_trip(self, tmp_artifacts):
        m = ResolvedManifest(
            profile_id="p1",
            stack_id="s1",
            fingerprint="abcdef1234567890",
            base_image="nvcr.io/nvidia/pytorch:24.06",
            python_version="Python 3.10.12",
            pip_freeze=["torch==2.1.0", "numpy==1.24.0"],
            npm_install_mode="lock_only",
            apt_install_mode="pin_only",
            tuple_id="x86_nvidia_cuda124_ubuntu2204",
            tuple_status="supported",
            tuple_mode="enforce",
            apt_packages=["git=1:2.39.2-1ubuntu1"],
            npm_packages=["next@15.0.0"],
            env=["PYTHONUNBUFFERED=1"],
            entrypoint=["python", "-m", "uvicorn"],
            variant_overrides={"precision": "bf16"},
            created_at="2025-01-01T00:00:00+00:00",
        )
        path = save_manifest(m)
        assert path.exists()

        loaded = load_manifest("abcdef1234567890")
        assert loaded.profile_id == "p1"
        assert loaded.pip_freeze == ["torch==2.1.0", "numpy==1.24.0"]
        assert loaded.npm_install_mode == "lock_only"
        assert loaded.apt_install_mode == "pin_only"
        assert loaded.tuple_id == "x86_nvidia_cuda124_ubuntu2204"
        assert loaded.npm_packages == ["next@15.0.0"]
        assert loaded.variant_overrides == {"precision": "bf16"}

    def test_missing_manifest_raises(self, tmp_artifacts):
        with pytest.raises(FileNotFoundError):
            load_manifest("0000000000000000")


class TestReproFingerprint:
    def test_repro_stack_has_distinct_id(self):
        from stackwarden.domain.repro import repro_stack_from_manifest
        from stackwarden.domain.models import StackSpec

        manifest = ResolvedManifest(
            profile_id="p1",
            stack_id="s1",
            fingerprint="fp1",
            base_image="base:latest",
            python_version="3.10",
            pip_freeze=["torch==2.1.0", "numpy==1.24.0"],
            apt_packages=["git=1:2.39"],
            npm_packages=["@types/node@22.0.0", "next@15.0.0"],
            env=[],
            entrypoint=["python"],
            variant_overrides={},
            created_at="2025-01-01T00:00:00",
        )

        original = StackSpec(
            id="s1",
            display_name="Test",
            task="llm",
            serve="vllm",
            api="fastapi",
            build_strategy="overlay",
            components={"base_role": "pytorch", "pip": [{"name": "torch"}], "apt": []},
            entrypoint={"cmd": ["python"]},
        )

        pinned = repro_stack_from_manifest(manifest, original)
        assert pinned.id != original.id
        assert "repro" in pinned.id
        assert len(pinned.components.pip) == 2
        assert pinned.components.pip[0].version == "==2.1.0"
        assert len(pinned.components.npm) == 2
        assert pinned.components.npm[0].version_mode == "custom"
        assert pinned.components.apt_install_mode == "pin_only"
        assert pinned.components.apt_constraints.get("git") == "=1:2.39"
