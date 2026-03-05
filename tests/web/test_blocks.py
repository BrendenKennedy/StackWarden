"""Tests for /api/blocks list/detail routes."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def data_dir(tmp_path):
    (tmp_path / "stacks").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "blocks").mkdir()
    return tmp_path


@pytest.fixture()
def client(data_dir):
    with patch.dict(
        os.environ,
        {"STACKWARDEN_DATA_DIR": str(data_dir), "STACKWARDEN_WEB_DEV": "true"},
    ):
        from stackwarden.web.app import create_app
        from stackwarden.web.settings import WebSettings

        app = create_app(WebSettings(token=None, dev=True))
        yield TestClient(app)


def _block_payload(id_: str) -> dict:
    return {
        "id": id_,
        "display_name": f"Block {id_}",
        "tags": ["api"],
        "build_strategy": "overlay",
        "base_role": "pytorch",
        "pip": [{"name": "fastapi", "version": "==0.115.*"}],
        "npm": [],
        "apt": [],
        "apt_constraints": {},
        "env": {},
        "ports": [8000],
        "entrypoint_cmd": ["python", "-m", "uvicorn"],
        "copy_items": [],
        "variants": {},
    }


class TestBlocksRoutes:
    def test_list_blocks(self, client):
        assert client.post("/api/blocks", json=_block_payload("fastapi")).status_code == 201
        assert client.post("/api/blocks", json=_block_payload("triton")).status_code == 201
        resp = client.get("/api/blocks")
        assert resp.status_code == 200
        ids = [b["id"] for b in resp.json()]
        assert "fastapi" in ids
        assert "triton" in ids

    def test_get_block(self, client):
        assert client.post("/api/blocks", json=_block_payload("fastapi")).status_code == 201
        resp = client.get("/api/blocks/fastapi")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "fastapi"
        assert body["pip_count"] == 1
        assert body["npm_count"] == 0

    def test_get_block_404(self, client):
        resp = client.get("/api/blocks/missing")
        assert resp.status_code == 404

    def test_delete_block(self, client):
        assert client.post("/api/blocks", json=_block_payload("delete-me")).status_code == 201
        deleted = client.delete("/api/blocks/delete-me")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True
        missing = client.get("/api/blocks/delete-me")
        assert missing.status_code == 404

