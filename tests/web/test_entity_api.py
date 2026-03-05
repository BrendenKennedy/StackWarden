"""Tests for entity-first API additions."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from stacksmith.domain.enums import ArtifactStatus
from stacksmith.domain.models import ArtifactRecord


@pytest.fixture()
def data_dir(tmp_path):
    (tmp_path / "stacks").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "blocks").mkdir()
    return tmp_path


def _stack_payload(id_: str = "entity-stack") -> dict:
    return {
        "kind": "stack_recipe",
        "id": id_,
        "display_name": "Entity Stack",
        "blocks": ["entity-block"],
        "build_strategy": "overlay",
        "base_role": "pytorch",
        "pip": [{"name": "fastapi", "version": ">=0.115"}],
        "npm": [],
        "apt": [],
        "apt_constraints": {},
        "env": {"MY_VAR": "hello"},
        "ports": [8080],
        "entrypoint_cmd": ["python", "-m", "uvicorn"],
        "copy_items": [],
        "variants": {},
    }


def _recipe_stack_payload(id_: str = "entity-recipe") -> dict:
    return {
        "kind": "stack_recipe",
        "schema_version": 3,
        "id": id_,
        "display_name": "Entity Recipe",
        "task": "custom",
        "serve": "python_api",
        "api": "fastapi",
        "blocks": ["entity-block"],
        "build_strategy": "overlay",
        "base_role": "pytorch",
        "pip": [],
        "npm": [],
        "apt": [],
        "apt_constraints": {},
        "env": {"MY_VAR": "hello"},
        "ports": [8080],
        "entrypoint_cmd": ["python", "-m", "uvicorn"],
        "copy_items": [],
        "variants": {},
    }


def _profile_payload(id_: str = "entity-profile") -> dict:
    return {
        "id": id_,
        "display_name": "Entity Profile",
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


def _block_payload(id_: str = "entity-block") -> dict:
    return {
        "id": id_,
        "display_name": "Entity Block",
        "tags": ["api"],
        "build_strategy": "overlay",
        "base_role": "pytorch",
        "pip": [{"name": "fastapi", "version": "==0.115.*"}],
        "npm": [],
        "apt": [],
        "apt_constraints": {},
        "env": {"MY_VAR": "hello"},
        "ports": [8000],
        "entrypoint_cmd": ["python", "-m", "uvicorn"],
        "copy_items": [],
        "variants": {},
    }


@pytest.fixture()
def client(data_dir):
    with patch.dict(
        os.environ,
        {"STACKSMITH_DATA_DIR": str(data_dir), "STACKSMITH_WEB_DEV": "true"},
    ):
        from stacksmith.catalog.store import CatalogStore
        from stacksmith.web.app import create_app
        from stacksmith.web.deps import get_catalog, get_job_manager
        from stacksmith.web.jobs.manager import JobManager
        from stacksmith.web.jobs.store import JobStore
        from stacksmith.web.settings import WebSettings

        catalog = CatalogStore(db_path=data_dir / "catalog.sqlite3")
        manager = JobManager(store=JobStore(db_path=data_dir / "catalog.sqlite3"))
        app = create_app(WebSettings(token=None, dev=True))
        app.dependency_overrides[get_catalog] = lambda: catalog
        app.dependency_overrides[get_job_manager] = lambda: manager
        yield TestClient(app), catalog, manager


def test_profile_detail_and_update(client):
    c, _catalog, _manager = client
    assert c.post("/api/profiles", json=_profile_payload()).status_code == 201

    detail = c.get("/api/profiles/entity-profile")
    assert detail.status_code == 200
    assert detail.json()["container_runtime"] == "nvidia"
    assert detail.json()["source"] == "local"
    spec = c.get("/api/profiles/entity-profile/spec")
    assert spec.status_code == 200
    assert spec.json()["id"] == "entity-profile"

    payload = _profile_payload()
    payload["display_name"] = "Entity Profile Updated"
    upd = c.put("/api/profiles/entity-profile", json=payload)
    assert upd.status_code == 200
    assert upd.json()["id"] == "entity-profile"

    payload_bad = _profile_payload(id_="different-id")
    bad = c.put("/api/profiles/entity-profile", json=payload_bad)
    assert bad.status_code == 422


def test_profile_delete(client):
    c, _catalog, _manager = client
    assert c.post("/api/profiles", json=_profile_payload(id_="entity-delete")).status_code == 201
    deleted = c.delete("/api/profiles/entity-delete")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    missing = c.get("/api/profiles/entity-delete")
    assert missing.status_code == 404


def test_stack_delete(client):
    c, _catalog, _manager = client
    assert c.post("/api/blocks", json=_block_payload()).status_code == 201
    assert c.post("/api/stacks", json=_stack_payload(id_="entity-stack-delete")).status_code == 201
    deleted = c.delete("/api/stacks/entity-stack-delete")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    missing = c.get("/api/stacks/entity-stack-delete")
    assert missing.status_code == 404


def test_stack_and_block_update(client):
    c, _catalog, _manager = client
    assert c.post("/api/blocks", json=_block_payload()).status_code == 201
    assert c.post("/api/stacks", json=_stack_payload()).status_code == 201

    s = _stack_payload()
    s["display_name"] = "Entity Stack Updated"
    s_spec = c.get("/api/stacks/entity-stack/spec")
    assert s_spec.status_code == 200
    su = c.put("/api/stacks/entity-stack", json=s)
    assert su.status_code == 200
    assert su.json()["id"] == "entity-stack"
    stack_detail = c.get("/api/stacks/entity-stack")
    assert stack_detail.status_code == 200
    assert stack_detail.json()["source"] == "local"

    b = _block_payload()
    b["display_name"] = "Entity Block Updated"
    b_spec = c.get("/api/blocks/entity-block/spec")
    assert b_spec.status_code == 200
    bu = c.put("/api/blocks/entity-block", json=b)
    assert bu.status_code == 200
    assert bu.json()["id"] == "entity-block"
    block_detail = c.get("/api/blocks/entity-block")
    assert block_detail.status_code == 200
    assert block_detail.json()["source"] == "local"


def test_stack_spec_preserves_recipe_shape(client):
    c, _catalog, _manager = client
    assert c.post("/api/blocks", json=_block_payload()).status_code == 201
    assert c.post("/api/stacks", json=_recipe_stack_payload()).status_code == 201
    spec = c.get("/api/stacks/entity-recipe/spec")
    assert spec.status_code == 200
    body = spec.json()
    assert body["kind"] == "stack_recipe"
    assert body["blocks"] == ["entity-block"]


def test_catalog_items_lifecycle_mapping(client):
    c, catalog, manager = client
    record = ArtifactRecord(
        id="art123",
        profile_id="p1",
        stack_id="s1",
        tag="local/stacksmith:test",
        fingerprint="fp123",
        base_image="python:3.12",
        build_strategy="overlay",
        status=ArtifactStatus.PLANNED,
        created_at=datetime.now(timezone.utc),
    )
    catalog.insert_artifact(record)
    manager.create_job(profile_id="p2", stack_id="s2", variants=None, flags={})

    resp = c.get("/api/catalog/items")
    assert resp.status_code == 200
    rows = resp.json()
    # Catalog shows artifacts only; jobs are accessed via Settings
    assert any(r["artifact_id"] == "art123" and r["status"] == "queued" for r in rows)


def test_catalog_items_pagination_applies_after_merge(client):
    c, catalog, manager = client
    now = datetime.now(timezone.utc)
    for idx in range(6):
        catalog.insert_artifact(
            ArtifactRecord(
                id=f"art-{idx}",
                profile_id="p",
                stack_id="s",
                tag=f"local/stacksmith:{idx}",
                fingerprint=f"fp-{idx}",
                base_image="python:3.12",
                build_strategy="overlay",
                status=ArtifactStatus.BUILT,
                created_at=now,
            )
        )

    first = c.get("/api/catalog/items?limit=3&offset=0")
    second = c.get("/api/catalog/items?limit=3&offset=3")
    assert first.status_code == 200
    assert second.status_code == 200
    first_ids = {row["row_id"] for row in first.json()}
    second_ids = {row["row_id"] for row in second.json()}
    assert len(first_ids) == 3
    assert len(second_ids) == 3
    assert first_ids.isdisjoint(second_ids)
