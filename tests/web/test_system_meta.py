"""Tests for system detection and create metadata endpoints."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from stacksmith.web.schemas import CudaDTO, DetectionHintsDTO, DetectionProbeDTO, GpuDTO


@pytest.fixture()
def client(tmp_path):
    (tmp_path / "stacks").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "blocks").mkdir()
    with patch.dict(os.environ, {"STACKSMITH_DATA_DIR": str(tmp_path), "STACKSMITH_WEB_DEV": "true"}):
        from stacksmith.web.app import create_app
        from stacksmith.web.settings import WebSettings

        app = create_app(WebSettings(token=None, dev=True))
        yield TestClient(app)


def test_detection_hints_returns_payload(client, monkeypatch):
    fake = DetectionHintsDTO(
        host_scope="server",
        arch="amd64",
        os="linux",
        container_runtime="nvidia",
        cuda_available=True,
        cuda=CudaDTO(major=12, minor=4, variant="cuda12.4"),
        gpu=GpuDTO(vendor="nvidia", family="ampere"),
        capabilities_suggested=["cuda"],
        cpu_model="AMD EPYC",
        cpu_cores_logical=32,
        memory_gb_total=251.5,
        probes=[DetectionProbeDTO(name="mock", status="ok", message="ok", duration_ms=1)],
    )
    monkeypatch.setattr("stacksmith.web.routes.detection.detect_server_hints", lambda: fake)

    resp = client.get("/api/system/detection-hints")
    assert resp.status_code == 200
    body = resp.json()
    assert body["host_scope"] == "server"
    assert body["arch"] == "amd64"
    assert body["cuda"]["major"] == 12
    assert body["cpu_model"] == "AMD EPYC"
    assert body["probes"][0]["name"] == "mock"


def test_detection_hints_refresh_bypasses_cache(client, monkeypatch):
    calls = {"count": 0}

    def _fake_detect():
        calls["count"] += 1
        return DetectionHintsDTO(
            host_scope="server",
            arch="amd64",
            os="linux",
            container_runtime="nvidia",
            cuda_available=False,
            capabilities_suggested=[],
            probes=[DetectionProbeDTO(name="mock", status="ok", message="ok", duration_ms=1)],
        )

    monkeypatch.setattr("stacksmith.web.routes.detection.detect_server_hints", _fake_detect)

    # Prime cache with patched detector and validate default cache reuse.
    resp1 = client.get("/api/system/detection-hints", params={"refresh": "true"})
    assert resp1.status_code == 200
    resp2 = client.get("/api/system/detection-hints")
    assert resp2.status_code == 200
    assert calls["count"] == 1

    resp3 = client.get("/api/system/detection-hints", params={"refresh": "true"})
    assert resp3.status_code == 200
    assert calls["count"] == 2


def test_create_contracts_shape(client):
    resp = client.get("/api/meta/create-contracts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["schema_version"] == 1
    assert "profile" in body
    assert "stack" in body
    assert "block" in body
    assert "required_fields" in body["profile"]
    assert "id" in body["profile"]["required_fields"]
    assert body["profile"]["fields"]["id"]["pattern"]
    assert "linux" in body["profile"]["fields"]["os"]["enum_values"]


def test_create_contracts_v2_shape(client):
    resp = client.get("/api/meta/create-contracts", params={"schema": "v2"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["schema_version"] == 2
    assert "base_candidates" not in body["profile"]["required_fields"]


def test_create_contracts_v3_declarative_fields_and_notes(client):
    resp = client.get("/api/meta/create-contracts", params={"schema": "v3"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["schema_version"] == 3

    profile_fields = body["profile"]["fields"]
    stack_fields = body["stack"]["fields"]

    for key in (
        "intent",
        "requirements",
        "derived_capabilities",
        "decision_trace",
        "selected_features",
        "rejected_candidates",
        "fix_suggestions",
    ):
        assert key in profile_fields
        assert profile_fields[key]["note"]
    assert "capabilities_mode" not in profile_fields
    assert "capabilities" not in profile_fields

    for key in (
        "intent",
        "requirements",
        "derived_capabilities",
        "decision_trace",
        "selected_features",
        "rejected_candidates",
        "fix_suggestions",
    ):
        assert key in stack_fields
        assert stack_fields[key]["note"]
    assert "blocks" in stack_fields
    assert "primary intent" in stack_fields["blocks"]["note"].lower()

    block_fields = body["block"]["fields"]
    assert "build_strategy" in block_fields
    assert "requires" in block_fields
    assert "npm[].package_manager" in block_fields
    assert "pip[].version_mode" in block_fields
    assert "pip_install_mode" in block_fields
    assert "pip_wheelhouse_path" in block_fields
    assert "npm_install_mode" in block_fields
    assert "apt_constraints" in block_fields
    assert "apt_install_mode" in block_fields
    assert body["block"]["defaults"]["requires.os"] == "linux"


def test_remote_detection_deferred(client):
    resp = client.post(
        "/api/system/detection-hints/remote",
        json={
            "host": "example.internal",
            "port": 22,
            "username": "ubuntu",
            "auth_mode": "ssh_key",
            "key_path": "~/.ssh/id_ed25519",
            "timeout_sec": 15,
        },
    )
    assert resp.status_code == 501
    body = resp.json()
    assert body["status"] == "deferred"
    assert resp.headers.get("Deprecation") == "true"
    assert resp.headers.get("Link") == '</api/system/detection-hints>; rel="successor-version"'


def test_system_config_includes_blocks_first_flag(client):
    resp = client.get("/api/system/config")
    assert resp.status_code == 200
    body = resp.json()
    assert "blocks_first_enabled" in body
    assert "tuple_layer_mode" in body


def test_settings_tuple_catalog_endpoint(client):
    resp = client.get("/api/settings/tuple-catalog")
    assert resp.status_code == 200
    body = resp.json()
    assert body["schema_version"] == 1
    assert "tuples" in body


def test_app_requires_token_outside_dev(tmp_path):
    with patch.dict(os.environ, {"STACKSMITH_DATA_DIR": str(tmp_path), "STACKSMITH_WEB_DEV": "true"}):
        from stacksmith.web.app import create_app
        from stacksmith.web.settings import WebSettings

        with pytest.raises(RuntimeError):
            create_app(WebSettings(token=None, dev=False))
