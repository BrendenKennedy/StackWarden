"""Tests for /api/layers list/detail routes."""

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
    xdg_config_home = data_dir / "xdg-config"
    xdg_config_home.mkdir(parents=True, exist_ok=True)
    with patch.dict(
        os.environ,
        {
            "STACKWARDEN_DATA_DIR": str(data_dir),
            "STACKWARDEN_WEB_DEV": "true",
            "XDG_CONFIG_HOME": str(xdg_config_home),
        },
    ):
        from stackwarden.web.app import create_app
        from stackwarden.web.deps import reset_cached_dependencies
        from stackwarden.web.settings import WebSettings

        reset_cached_dependencies()
        app = create_app(WebSettings(token=None, dev=True))
        client = TestClient(app)
        client.post(
            "/api/auth/setup",
            json={"username": "admin", "password": "dev-password-123"},
        )
        yield client


def _layer_payload(
    id_: str,
    *,
    stack_layer: str = "serving_layer",
    tags: list[str] | None = None,
    incompatible_with: list[str] | None = None,
) -> dict:
    return {
        "id": id_,
        "display_name": f"Layer {id_}",
        "stack_layer": stack_layer,
        "tags": tags or ["api"],
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
        "incompatible_with": incompatible_with or [],
    }


class TestLayersRoutes:
    def test_list_layers(self, client):
        assert client.post("/api/layers", json=_layer_payload("fastapi")).status_code == 201
        assert client.post("/api/layers", json=_layer_payload("triton")).status_code == 201
        resp = client.get("/api/layers")
        assert resp.status_code == 200
        ids = [b["id"] for b in resp.json()]
        assert "fastapi" in ids
        assert "triton" in ids

    def test_get_layer(self, client):
        assert client.post("/api/layers", json=_layer_payload("fastapi")).status_code == 201
        resp = client.get("/api/layers/fastapi")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "fastapi"
        assert body["pip_count"] == 1
        assert body["npm_count"] == 0

    def test_get_layer_404(self, client):
        resp = client.get("/api/layers/missing")
        assert resp.status_code == 404

    def test_delete_layer(self, client):
        assert client.post("/api/layers", json=_layer_payload("delete-me")).status_code == 201
        deleted = client.delete("/api/layers/delete-me")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True
        missing = client.get("/api/layers/delete-me")
        assert missing.status_code == 404

    def test_classify_layer_options_groups_and_flags_incompatible(self, client):
        profile_resp = client.post(
            "/api/profiles",
            json={
                "id": "p-test",
                "display_name": "P Test",
                "arch": "amd64",
                "os": "linux",
                "container_runtime": "nvidia",
                "gpu": {"vendor": "nvidia", "family": "ampere"},
                "base_candidates": [{"name": "python", "tags": ["3.12-slim"], "score_bias": 0}],
            },
        )
        assert profile_resp.status_code == 201

        assert (
            client.post(
                "/api/layers",
                json=_layer_payload(
                    "runtime_cpu",
                    stack_layer="system_runtime_layer",
                    tags=["runtime", "cpu"],
                ),
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/layers",
                json=_layer_payload(
                    "cuda_runtime",
                    stack_layer="driver_accelerator_layer",
                    tags=["cuda", "accelerator"],
                    incompatible_with=["runtime_cpu"],
                ),
            ).status_code
            == 201
        )

        resp = client.post(
            "/api/layers/options/classify",
            json={
                "selected_layers": ["runtime_cpu"],
                "inference_type": "diffusion",
                "inference_profile": "latency",
                "target_profile_id": "p-test",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        groups = {group["stack_layer"]: group["options"] for group in body["groups"]}
        assert "driver_accelerator_layer" in groups
        cuda = next(option for option in groups["driver_accelerator_layer"] if option["id"] == "cuda_runtime")
        assert cuda["tier"] == "incompatible"
        assert any("runtime_cpu" in reason for reason in cuda["reasons"])

    def test_classify_layer_options_group_order_is_high_to_low(self, client):
        profile_resp = client.post(
            "/api/profiles",
            json={
                "id": "p-order",
                "display_name": "P Order",
                "arch": "amd64",
                "os": "linux",
                "container_runtime": "nvidia",
                "gpu": {"vendor": "nvidia", "family": "ampere"},
                "base_candidates": [{"name": "python", "tags": ["3.12-slim"], "score_bias": 0}],
            },
        )
        assert profile_resp.status_code == 201

        resp = client.post(
            "/api/layers/options/classify",
            json={
                "selected_layers": [],
                "inference_type": "vision",
                "inference_profile": "balanced",
                "target_profile_id": "p-order",
            },
        )
        assert resp.status_code == 200
        layer_order = [group["stack_layer"] for group in resp.json()["groups"]]
        assert layer_order == [
            "inference_engine_layer",
            "optimization_compilation_layer",
            "core_compute_layer",
            "driver_accelerator_layer",
            "system_runtime_layer",
            "application_orchestration_layer",
            "observability_operations_layer",
            "serving_layer",
        ]

    def test_classify_layer_options_vision_has_multiple_compatible_runtimes(self, client):
        profile_resp = client.post(
            "/api/profiles",
            json={
                "id": "p-vision",
                "display_name": "P Vision",
                "arch": "amd64",
                "os": "linux",
                "container_runtime": "nvidia",
                "gpu": {"vendor": "nvidia", "family": "ampere"},
                "base_candidates": [{"name": "python", "tags": ["3.12-slim"], "score_bias": 0}],
            },
        )
        assert profile_resp.status_code == 201

        assert (
            client.post(
                "/api/layers",
                json=_layer_payload(
                    "vision_onnx_runtime",
                    stack_layer="inference_engine_layer",
                    tags=["vision", "onnx", "classification"],
                ),
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/layers",
                json=_layer_payload(
                    "ultralytics_vision_runtime",
                    stack_layer="inference_engine_layer",
                    tags=["vision", "detector", "segmentation"],
                ),
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/layers",
                json=_layer_payload(
                    "torchvision_vision_runtime",
                    stack_layer="inference_engine_layer",
                    tags=["vision", "classification"],
                ),
            ).status_code
            == 201
        )

        resp = client.post(
            "/api/layers/options/classify",
            json={
                "selected_layers": [],
                "inference_type": "vision",
                "inference_profile": "balanced",
                "target_profile_id": "p-vision",
            },
        )
        assert resp.status_code == 200
        groups = {group["stack_layer"]: group["options"] for group in resp.json()["groups"]}
        compatible = [
            option["id"]
            for option in groups["inference_engine_layer"]
            if option["tier"] in {"recommended", "compatible"}
        ]
        assert "vision_onnx_runtime" in compatible
        assert "ultralytics_vision_runtime" in compatible
        assert "torchvision_vision_runtime" in compatible

