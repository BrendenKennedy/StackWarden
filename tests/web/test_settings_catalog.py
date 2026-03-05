from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    (tmp_path / "stacks").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "blocks").mkdir()
    monkeypatch.setenv("STACKSMITH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STACKSMITH_WEB_DEV", "true")
    monkeypatch.setenv("STACKSMITH_WEB_ADMIN_TOKEN", "admin-secret")
    with patch.dict(
        os.environ,
        {
            "STACKSMITH_DATA_DIR": str(tmp_path),
            "STACKSMITH_WEB_DEV": "true",
            "STACKSMITH_WEB_ADMIN_TOKEN": "admin-secret",
        },
    ):
        from stacksmith.web.app import create_app
        from stacksmith.web.settings import WebSettings

        app = create_app(WebSettings(token=None, dev=True))
        yield TestClient(app)


def test_get_hardware_catalogs(client):
    resp = client.get("/api/settings/hardware-catalogs")
    assert resp.status_code == 200
    body = resp.json()
    assert "arch" in body
    assert "gpu_vendor" in body


def test_get_block_catalog(client):
    resp = client.get("/api/settings/block-catalog")
    assert resp.status_code == 200
    body = resp.json()
    assert "categories" in body
    assert "presets" in body
    assert len(body["presets"]) >= 80
    assert any(p["id"] == "vllm" for p in body["presets"])
    assert any(p["id"] == "diffusers_runtime" for p in body["presets"])


def test_upsert_hardware_catalog_item_requires_admin_header(client):
    body = {
        "catalog": "gpu_model",
        "expected_revision": 1,
        "item": {"id": "h100", "label": "H100", "aliases": [], "parent_id": "hopper", "deprecated": False},
    }
    denied = client.post("/api/settings/hardware-catalogs/gpu_model", json=body)
    assert denied.status_code == 403

    allowed = client.post(
        "/api/settings/hardware-catalogs/gpu_model",
        json=body,
        headers={"X-Stacksmith-Admin-Token": "admin-secret"},
    )
    assert allowed.status_code == 200
    assert any(i["id"] == "h100" for i in allowed.json()["gpu_model"])


def test_update_settings_config_remote_catalog(client):
    resp = client.post(
        "/api/settings/config",
        json={
            "remote_catalog_enabled": True,
            "remote_catalog_repo_url": "https://example.com/org/stacksmith-data.git",
            "remote_catalog_branch": "main",
            "remote_catalog_local_path": "/tmp/stacksmith-remote-data",
            "remote_catalog_local_overrides_path": "/tmp/stacksmith-local-overrides",
            "remote_catalog_auto_pull": True,
            "sync_now": False,
        },
        headers={"X-Stacksmith-Admin-Token": "admin-secret"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["remote_catalog_enabled"] is True
    assert body["remote_catalog_repo_url"] == "https://example.com/org/stacksmith-data.git"
    assert body["remote_catalog_branch"] == "main"
    assert body["remote_catalog_local_path"] == "/tmp/stacksmith-remote-data"
    assert body["remote_catalog_local_overrides_path"] == "/tmp/stacksmith-local-overrides"
    assert body["remote_catalog_auto_pull"] is True


def test_update_settings_config_can_sync_now(client, monkeypatch):
    monkeypatch.setattr(
        "stacksmith.web.routes.settings.sync_remote_catalog",
        lambda _cfg: SimpleNamespace(
            status="ok",
            detail="synced",
            commit="abc123",
            local_path="/tmp/stacksmith-remote-data",
        ),
    )
    resp = client.post(
        "/api/settings/config",
        json={
            "remote_catalog_enabled": True,
            "remote_catalog_repo_url": "https://example.com/org/stacksmith-data.git",
            "sync_now": True,
        },
        headers={"X-Stacksmith-Admin-Token": "admin-secret"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["remote_catalog_last_sync_status"] == "ok"
    assert body["remote_catalog_last_sync_detail"] == "synced"
    assert body["remote_catalog_last_sync_commit"] == "abc123"
