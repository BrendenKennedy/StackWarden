"""Resilience tests for profile metadata/list endpoints."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path):
    (tmp_path / "stacks").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "blocks").mkdir()
    with patch.dict(
        os.environ,
        {"STACKWARDEN_DATA_DIR": str(tmp_path), "STACKWARDEN_WEB_DEV": "true"},
    ):
        from stackwarden.web.app import create_app
        from stackwarden.web.settings import WebSettings

        app = create_app(WebSettings(token=None, dev=True))
        yield TestClient(app), tmp_path


def test_list_profiles_skips_malformed_records(client):
    c, root = client
    profiles_dir = root / "profiles"

    (profiles_dir / "good.yaml").write_text(
        "\n".join(
            [
                "schema_version: 2",
                "id: good",
                "display_name: Good",
                "arch: amd64",
                "os: linux",
                "container_runtime: nvidia",
                "gpu:",
                "  vendor: nvidia",
                "  family: ampere",
                "capabilities: [cuda]",
            ]
        )
    )
    (profiles_dir / "bad.yaml").write_text(
        "\n".join(
            [
                "schema_version: 2",
                "id: bad",
                "display_name: Bad",
                "arch: definitely_not_real",
                "os: linux",
                "container_runtime: nvidia",
                "gpu:",
                "  vendor: nvidia",
                "  family: ampere",
            ]
        )
    )

    resp = c.get("/api/profiles")
    assert resp.status_code == 200
    rows = resp.json()
    assert [r["id"] for r in rows] == ["good"]
    assert resp.headers.get("X-StackWarden-Profiles-Skipped") == "1"


def test_list_stacks_skips_malformed_records(client):
    c, root = client
    stacks_dir = root / "stacks"
    (stacks_dir / "good.yaml").write_text(
        "\n".join(
            [
                "schema_version: 2",
                "kind: stack",
                "id: good",
                "display_name: Good",
                "task: custom",
                "serve: python_api",
                "api: none",
                "build_strategy: overlay",
                "components:",
                "  base_role: python",
                "entrypoint:",
                "  cmd: ['python', '-V']",
            ]
        )
    )
    (stacks_dir / "bad.yaml").write_text("id: bad\nbuild_strategy: nope")

    resp = c.get("/api/stacks")
    assert resp.status_code == 200
    assert [r["id"] for r in resp.json()] == ["good"]
    assert resp.headers.get("X-StackWarden-Stacks-Skipped") == "1"


def test_list_blocks_skips_malformed_records(client):
    c, root = client
    blocks_dir = root / "blocks"
    (blocks_dir / "good.yaml").write_text(
        "\n".join(
            [
                "schema_version: 2",
                "kind: block",
                "id: good",
                "display_name: Good",
                "tags: []",
                "build_strategy: overlay",
                "components:",
                "  base_role: python",
                "entrypoint:",
                "  cmd: ['python', '-V']",
            ]
        )
    )
    (blocks_dir / "bad.yaml").write_text("schema_version: 2\nid: bad\ncomponents: 1")

    resp = c.get("/api/blocks")
    assert resp.status_code == 200
    assert [r["id"] for r in resp.json()] == ["good"]
    assert resp.headers.get("X-StackWarden-Blocks-Skipped") == "1"

