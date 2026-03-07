from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    (tmp_path / "stacks").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "layers").mkdir()
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STACKWARDEN_WEB_DEV", "true")
    with patch.dict(
        os.environ,
        {
            "STACKWARDEN_DATA_DIR": str(tmp_path),
            "STACKWARDEN_WEB_DEV": "true",
        },
    ):
        from stackwarden.web.app import create_app
        from stackwarden.web.deps import reset_cached_dependencies
        from stackwarden.web.settings import WebSettings

        reset_cached_dependencies()
        app = create_app(WebSettings(token=None, dev=True))
        with TestClient(app) as test_client:
            test_client.post(
                "/api/auth/setup",
                json={"username": "admin", "password": "dev-password-123"},
            )
            yield test_client


def test_get_hardware_catalogs(client):
    resp = client.get("/api/settings/hardware-catalogs")
    assert resp.status_code == 200
    body = resp.json()
    assert "arch" in body
    assert "gpu_vendor" in body


def test_get_layer_catalog(client):
    resp = client.get("/api/settings/layer-catalog")
    assert resp.status_code == 200
    body = resp.json()
    assert "categories" in body
    assert "presets" in body
    assert len(body["presets"]) >= 20
    assert any(p["id"] == "vllm_model_runtime" for p in body["presets"])
    assert any(p["id"] == "flux_schnell_runtime" for p in body["presets"])


def test_upsert_hardware_catalog_item_with_session_auth(client):
    body = {
        "catalog": "gpu_model",
        "expected_revision": 1,
        "item": {"id": "h100", "label": "H100", "aliases": [], "parent_id": "hopper", "deprecated": False},
    }
    allowed = client.post(
        "/api/settings/hardware-catalogs/gpu_model",
        json=body,
    )
    assert allowed.status_code == 200
    assert any(i["id"] == "h100" for i in allowed.json()["gpu_model"])


def test_update_settings_config_catalog_paths(client):
    resp = client.post(
        "/api/settings/config",
        json={
            "catalog_local_path": "/tmp/stackwarden-catalog-data",
            "catalog_local_overrides_path": "/tmp/stackwarden-local-overrides",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["catalog_local_path"] == "/tmp/stackwarden-catalog-data"
    assert body["catalog_local_overrides_path"] == "/tmp/stackwarden-local-overrides"


def test_deleting_default_profile_clears_config_default(client, monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    profile_id = "default-profile-delete"
    payload = {
        "id": profile_id,
        "display_name": "Default Delete Profile",
        "arch": "amd64",
        "os": "linux",
        "container_runtime": "nvidia",
        "cuda": {"major": 12, "minor": 5, "variant": "runtime"},
        "gpu": {"vendor": "nvidia", "family": "ampere"},
        "capabilities": ["cuda"],
        "base_candidates": [{"name": "nvcr.io/nvidia/pytorch", "tags": ["24.06-py3"], "score_bias": 0}],
        "constraints": {"disallow": {}, "require": {}},
        "defaults": {"python": "3.10", "user": "root", "workdir": "/workspace"},
    }
    created = client.post("/api/profiles", json=payload)
    assert created.status_code == 201

    cfg_set = client.post("/api/settings/config", json={"default_profile": profile_id})
    assert cfg_set.status_code == 200
    assert cfg_set.json()["default_profile"] == profile_id

    deleted = client.delete(f"/api/profiles/{profile_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    listed_after_delete = client.get("/api/profiles")
    assert listed_after_delete.status_code == 200
    assert all(item["id"] != profile_id for item in listed_after_delete.json())

    cfg_after = client.get("/api/system/config")
    assert cfg_after.status_code == 200
    assert cfg_after.json()["default_profile"] is None

    recreated = client.post("/api/profiles", json=payload)
    assert recreated.status_code == 201
