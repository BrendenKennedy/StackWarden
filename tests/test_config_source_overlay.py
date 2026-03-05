from __future__ import annotations

import os
from pathlib import Path

import yaml

from stackwarden.config import (
    get_profile_origin,
    get_profiles_dir,
    list_profile_ids,
    load_profile,
)


def _profile_yaml(profile_id: str, display_name: str) -> dict:
    return {
        "schema_version": 1,
        "id": profile_id,
        "display_name": display_name,
        "arch": "amd64",
        "os": "linux",
        "container_runtime": "nvidia",
        "cuda": {"major": 12, "minor": 4, "variant": "cuda12.4"},
        "gpu": {"vendor": "nvidia", "family": "ampere"},
        "base_candidates": [
            {"name": "nvcr.io/nvidia/pytorch", "tags": ["24.06-py3"], "score_bias": 100}
        ],
    }


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")


def test_remote_overlay_prefers_local_overrides(tmp_path, monkeypatch):
    config_root = tmp_path / "config-root"
    remote_root = tmp_path / "remote-catalog"
    local_root = tmp_path / "local-catalog"

    _write_yaml(
        config_root / "stackwarden" / "config.yaml",
        {
            "remote_catalog": {
                "enabled": True,
                "repo_url": "https://github.com/acme/stackwarden-catalog.git",
                "branch": "main",
                "local_path": str(remote_root),
                "local_overrides_path": str(local_root),
                "auto_pull": True,
            }
        },
    )

    _write_yaml(
        remote_root / "profiles" / "my_profile.yaml",
        _profile_yaml("my_profile", "Remote Profile"),
    )
    _write_yaml(
        local_root / "profiles" / "my_profile.yaml",
        _profile_yaml("my_profile", "Local Override Profile"),
    )
    _write_yaml(
        remote_root / "profiles" / "remote_only.yaml",
        _profile_yaml("remote_only", "Remote Only Profile"),
    )

    monkeypatch.delenv("STACKWARDEN_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_root))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    loaded = load_profile("my_profile")
    assert loaded.display_name == "Local Override Profile"
    profile_ids = list_profile_ids()
    assert "my_profile" in profile_ids
    assert "remote_only" in profile_ids

    local_origin = get_profile_origin("my_profile")
    assert local_origin is not None
    assert local_origin["source"] == "local"

    remote_origin = get_profile_origin("remote_only")
    assert remote_origin is not None
    assert remote_origin["source"] == "remote"
    assert remote_origin["source_repo_url"] == "https://github.com/acme/stackwarden-catalog.git"
    assert remote_origin["source_repo_owner"] == "acme"

    assert get_profiles_dir() == local_root / "profiles"

