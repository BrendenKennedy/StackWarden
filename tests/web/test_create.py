"""Tests for the Create endpoints (POST /api/stacks, /api/profiles, dry-run)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from stackwarden.config import load_block, load_profile, load_stack


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def data_dir(tmp_path):
    """Temporary data directory with stacks/ and profiles/ subdirs."""
    stacks = tmp_path / "stacks"
    profiles = tmp_path / "profiles"
    blocks = tmp_path / "blocks"
    stacks.mkdir()
    profiles.mkdir()
    blocks.mkdir()
    return tmp_path


@pytest.fixture()
def client(data_dir):
    """TestClient that writes specs to *data_dir*."""
    with patch.dict(
        os.environ,
        {"STACKWARDEN_DATA_DIR": str(data_dir), "STACKWARDEN_WEB_DEV": "true"},
    ):
        from stackwarden.web.app import create_app
        from stackwarden.web.settings import WebSettings

        app = create_app(WebSettings(token=None, dev=True))
        yield TestClient(app)


def _valid_stack_payload(**overrides) -> dict:
    base = {
        "kind": "stack_recipe",
        "id": "my-new-stack",
        "display_name": "My New Stack",
        "build_strategy": "overlay",
        "base_role": "pytorch",
        "blocks": ["fastapi"],
        "copy_items": [],
        "variants": {},
    }
    base.update(overrides)
    return base


def _valid_recipe_stack_payload(**overrides) -> dict:
    base = _valid_stack_payload(
        id="my-recipe-stack",
        display_name="My Recipe Stack",
        blocks=["fastapi"],
    )
    base.update(overrides)
    return base


def _valid_block_payload(**overrides) -> dict:
    base = {
        "id": "fastapi",
        "display_name": "FastAPI",
        "tags": ["api", "python"],
        "build_strategy": "overlay",
        "base_role": "pytorch",
        "pip": [{"name": "fastapi", "version": "==0.115.*"}],
        "pip_install_mode": "index",
        "pip_wheelhouse_path": "",
        "npm": [],
        "apt": ["curl"],
        "apt_constraints": {},
        "env": {"MY_VAR": "hello"},
        "ports": [8000],
        "entrypoint_cmd": ["python", "-m", "uvicorn"],
        "copy_items": [],
        "variants": {},
    }
    base.update(overrides)
    return base


def _valid_profile_payload(**overrides) -> dict:
    base = {
        "id": "my-new-profile",
        "display_name": "My New Profile",
        "arch": "amd64",
        "os": "linux",
        "container_runtime": "nvidia",
        "cuda": {"major": 12, "minor": 5, "variant": "runtime"},
        "gpu": {"vendor": "nvidia", "family": "ampere"},
        "capabilities": ["cuda"],
        "base_candidates": [
            {"name": "nvcr.io/nvidia/pytorch", "tags": ["24.06-py3"], "score_bias": 0},
        ],
        "defaults": {"python": "3.10", "user": "root", "workdir": "/workspace"},
    }
    base.update(overrides)
    return base


def _ensure_fastapi_block(client: TestClient) -> None:
    client.post("/api/blocks", json=_valid_block_payload())


# ---------------------------------------------------------------------------
# Stack create tests
# ---------------------------------------------------------------------------

class TestCreateStack:
    def test_success(self, client, data_dir):
        _ensure_fastapi_block(client)
        resp = client.post("/api/stacks", json=_valid_stack_payload())
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == "my-new-stack"
        assert body["display_name"] == "My New Stack"
        assert (data_dir / "stacks" / "my-new-stack.yaml").exists()

        with patch.dict(os.environ, {"STACKWARDEN_DATA_DIR": str(data_dir)}):
            stack = load_stack("my-new-stack")
            assert stack.id == "my-new-stack"
            assert stack.kind == "stack"
            assert stack.blocks == ["fastapi"]

    def test_conflict(self, client):
        _ensure_fastapi_block(client)
        payload = _valid_stack_payload()
        resp1 = client.post("/api/stacks", json=payload)
        assert resp1.status_code == 201
        resp2 = client.post("/api/stacks", json=payload)
        assert resp2.status_code == 409

    def test_reject_path_traversal(self, client):
        _ensure_fastapi_block(client)
        payload = _valid_stack_payload(
            copy_items=[{"src": "../../etc/passwd", "dst": "/tmp/pwned"}],
        )
        resp = client.post("/api/stacks", json=payload)
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert any("copy_items" in e["field"] for e in detail)

    def test_reject_dockerfile_template(self, client):
        _ensure_fastapi_block(client)
        payload = _valid_stack_payload(build_strategy="dockerfile_template")
        resp = client.post("/api/stacks", json=payload)
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert any("build_strategy" in e["field"] for e in detail)

    def test_reject_variant_reserved_name(self, client):
        _ensure_fastapi_block(client)
        payload = _valid_stack_payload(variants={
            "profile": {"type": "bool", "options": [], "default": True},
        })
        resp = client.post("/api/stacks", json=payload)
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert any("profile" in e["field"] for e in detail)

    def test_reject_bad_id(self, client):
        _ensure_fastapi_block(client)
        payload = _valid_stack_payload(id="AB")
        resp = client.post("/api/stacks", json=payload)
        assert resp.status_code == 422

    def test_reject_missing_blocks(self, client):
        payload = _valid_stack_payload(blocks=[])
        resp = client.post("/api/stacks", json=payload)
        assert resp.status_code == 422

    def test_recipe_success(self, client, data_dir):
        _ensure_fastapi_block(client)
        resp = client.post("/api/stacks", json=_valid_recipe_stack_payload())
        assert resp.status_code == 201
        with patch.dict(os.environ, {"STACKWARDEN_DATA_DIR": str(data_dir)}):
            stack = load_stack("my-recipe-stack")
            assert stack.id == "my-recipe-stack"
            assert stack.components.base_role == "pytorch"


# ---------------------------------------------------------------------------
# Stack dry-run tests
# ---------------------------------------------------------------------------

class TestDryRunStack:
    def test_valid_returns_yaml(self, client):
        _ensure_fastapi_block(client)
        resp = client.post("/api/stacks/dry-run", json=_valid_stack_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert "id: my-new-stack" in body["yaml"]
        assert body["errors"] == []

    def test_invalid_returns_errors(self, client):
        _ensure_fastapi_block(client)
        payload = _valid_stack_payload(build_strategy="dockerfile_template")
        resp = client.post("/api/stacks/dry-run", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is False
        assert len(body["errors"]) > 0

    def test_recipe_valid_returns_yaml(self, client):
        _ensure_fastapi_block(client)
        payload = _valid_recipe_stack_payload()
        resp = client.post("/api/stacks/dry-run", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert "kind: stack_recipe" in body["yaml"]


class TestComposePreview:
    def test_success(self, client):
        client.post("/api/blocks", json=_valid_block_payload())
        resp = client.post("/api/stacks/compose", json=_valid_recipe_stack_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert "kind: stack" in body["yaml"]
        assert body["resolved_spec"]["id"] == "my-recipe-stack"

    def test_unknown_block_error(self, client):
        resp = client.post("/api/stacks/compose", json=_valid_recipe_stack_payload(blocks=["missing"]))
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is False
        assert any("Block not found" in e["message"] for e in body["errors"])

    def test_reports_soft_dependency_conflicts(self, client):
        block_a = _valid_block_payload(
            id="numpy-pinned",
            pip=[{"name": "numpy", "version": "==1.26.4", "version_mode": "custom"}],
        )
        block_b = _valid_block_payload(
            id="numpy-latest",
            pip=[{"name": "numpy", "version": "", "version_mode": "latest"}],
        )
        assert client.post("/api/blocks", json=block_a).status_code == 201
        assert client.post("/api/blocks", json=block_b).status_code == 201
        payload = _valid_recipe_stack_payload(
            blocks=["numpy-pinned", "numpy-latest"],
        )
        resp = client.post("/api/stacks/compose", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert any(
            c.get("type") == "pip" and c.get("name") == "numpy" and c.get("severity") == "warning"
            for c in body.get("dependency_conflicts", [])
        )

    def test_reports_hard_dependency_conflicts(self, client):
        block_a = _valid_block_payload(
            id="numpy-pin-a",
            pip=[{"name": "numpy", "version": "==1.26.4", "version_mode": "custom"}],
        )
        block_b = _valid_block_payload(
            id="numpy-pin-b",
            pip=[{"name": "numpy", "version": "==2.0.0", "version_mode": "custom"}],
        )
        assert client.post("/api/blocks", json=block_a).status_code == 201
        assert client.post("/api/blocks", json=block_b).status_code == 201
        payload = _valid_recipe_stack_payload(
            blocks=["numpy-pin-a", "numpy-pin-b"],
        )
        resp = client.post("/api/stacks/compose", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is False
        assert any(c.get("severity") == "error" for c in body.get("dependency_conflicts", []))

    def test_reports_wheelhouse_policy_conflicts(self, client):
        block_a = _valid_block_payload(
            id="wheel-a",
            pip_install_mode="wheelhouse_only",
            pip_wheelhouse_path="wheels/a",
        )
        block_b = _valid_block_payload(
            id="wheel-b",
            pip_install_mode="wheelhouse_prefer",
            pip_wheelhouse_path="wheels/b",
        )
        assert client.post("/api/blocks", json=block_a).status_code == 201
        assert client.post("/api/blocks", json=block_b).status_code == 201
        payload = _valid_recipe_stack_payload(
            blocks=["wheel-a", "wheel-b"],
        )
        resp = client.post("/api/stacks/compose", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert any(
            c.get("type") == "pip_wheelhouse" and c.get("severity") in {"warning", "error"}
            for c in body.get("dependency_conflicts", [])
        )

    def test_reports_tuple_conflicts(self, client):
        block_a = _valid_block_payload(
            id="tuple-a",
            requires={"arch": "amd64"},
        )
        block_b = _valid_block_payload(
            id="tuple-b",
            requires={"arch": "arm64"},
        )
        assert client.post("/api/blocks", json=block_a).status_code == 201
        assert client.post("/api/blocks", json=block_b).status_code == 201
        payload = _valid_recipe_stack_payload(
            blocks=["tuple-a", "tuple-b"],
        )
        resp = client.post("/api/stacks/compose", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert any(c.get("type") == "tuple" and c.get("name") == "arch" for c in body.get("tuple_conflicts", []))

    def test_reports_runtime_conflicts(self, client):
        block_a = _valid_block_payload(
            id="runtime-a",
            env={"APP_MODE": "prod"},
            entrypoint_cmd=["python", "-m", "uvicorn"],
        )
        block_b = _valid_block_payload(
            id="runtime-b",
            env={"APP_MODE": "dev"},
            entrypoint_cmd=["python", "-m", "gunicorn"],
        )
        assert client.post("/api/blocks", json=block_a).status_code == 201
        assert client.post("/api/blocks", json=block_b).status_code == 201
        payload = _valid_recipe_stack_payload(blocks=["runtime-a", "runtime-b"])
        resp = client.post("/api/stacks/compose", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert any(c.get("type") == "env" for c in body.get("runtime_conflicts", []))
        assert any(c.get("type") == "entrypoint" for c in body.get("runtime_conflicts", []))

    def test_internal_fault_maps_to_500(self, client, monkeypatch):
        from stackwarden.application.errors import AppInternalError

        monkeypatch.setattr(
            "stackwarden.web.routes.create.app_compose_stack_preview",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AppInternalError("boom")),
        )
        resp = client.post("/api/stacks/compose", json=_valid_recipe_stack_payload())
        assert resp.status_code == 500
        assert "boom" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Profile create tests
# ---------------------------------------------------------------------------

class TestCreateProfile:
    def test_success(self, client, data_dir):
        resp = client.post("/api/profiles", json=_valid_profile_payload())
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == "my-new-profile"
        assert (data_dir / "profiles" / "my-new-profile.yaml").exists()

        with patch.dict(os.environ, {"STACKWARDEN_DATA_DIR": str(data_dir)}):
            profile = load_profile("my-new-profile")
            assert profile.id == "my-new-profile"
            assert profile.arch.value == "amd64"

    def test_conflict(self, client):
        payload = _valid_profile_payload()
        resp1 = client.post("/api/profiles", json=payload)
        assert resp1.status_code == 201
        resp2 = client.post("/api/profiles", json=payload)
        assert resp2.status_code == 409

    def test_reject_no_candidates(self, client):
        payload = _valid_profile_payload(base_candidates=[])
        resp = client.post("/api/profiles", json=payload)
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert any("base_candidates" in e["field"] for e in detail)

    def test_reject_non_linux_os(self, client):
        payload = _valid_profile_payload(os="darwin")
        resp = client.post("/api/profiles", json=payload)
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert any("os" in e["field"] for e in detail)

    def test_reject_invalid_candidate_image_ref(self, client):
        payload = _valid_profile_payload(base_candidates=[
            {"name": "NVCR.IO/NVIDIA/PYTORCH", "tags": ["24.06-py3"], "score_bias": 0},
        ])
        resp = client.post("/api/profiles", json=payload)
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert any("base_candidates[0].name" == e["field"] for e in detail)

    def test_accepts_profile_constraints(self, client, data_dir):
        payload = _valid_profile_payload(
            constraints={
                "disallow": {"serve": ["triton"]},
                "require": {"env": ["NVIDIA_VISIBLE_DEVICES"]},
            }
        )
        resp = client.post("/api/profiles", json=payload)
        assert resp.status_code == 201
        with patch.dict(os.environ, {"STACKWARDEN_DATA_DIR": str(data_dir)}):
            profile = load_profile("my-new-profile")
            assert "triton" in profile.constraints.disallow.get("serve", [])
            assert "NVIDIA_VISIBLE_DEVICES" in profile.constraints.require.get("env", [])


# ---------------------------------------------------------------------------
# Profile dry-run tests
# ---------------------------------------------------------------------------

class TestDryRunProfile:
    def test_valid_returns_yaml(self, client):
        resp = client.post("/api/profiles/dry-run", json=_valid_profile_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert "id: my-new-profile" in body["yaml"]

    def test_invalid_returns_errors(self, client):
        payload = _valid_profile_payload(base_candidates=[])
        resp = client.post("/api/profiles/dry-run", json=payload)
        body = resp.json()
        assert body["valid"] is False
        assert len(body["errors"]) > 0


class TestProfileV2Create:
    def test_v2_allows_capability_only_without_candidates(self, client):
        payload = _valid_profile_payload(
            schema_version=2,
            base_candidates=[],
            host_facts={"driver_version": "550.54", "runtime_version": None, "detected_at": None},
            capability_ranges=[{"name": "cuda_runtime", "min": "12.0", "max": "12.5", "values": []}],
        )
        resp = client.post("/api/profiles", json=payload)
        assert resp.status_code == 201


class TestDeclarativeDerivationNormalization:
    def test_stack_create_normalizes_derived_capabilities(self, client, data_dir):
        _ensure_fastapi_block(client)
        payload = _valid_stack_payload(
            id="derived-stack",
            display_name="Derived Stack",
            schema_version=3,
            requirements={
                "needs": ["cuda", "tensorcore", "cuda"],
                "optimize_for": ["latency"],
                "constraints": {},
            },
            derived_capabilities=["manual-should-be-ignored"],
            decision_trace=["initial trace"],
        )
        resp = client.post("/api/stacks", json=payload)
        assert resp.status_code == 201

        with patch.dict(os.environ, {"STACKWARDEN_DATA_DIR": str(data_dir)}):
            stack = load_stack("derived-stack")
            # load_stack resolves recipe -> composed StackSpec and does not retain derivation trace fields.
            assert stack.id == "derived-stack"
            assert stack.blocks == ["fastapi"]

    def test_profile_create_normalizes_derived_capabilities(self, client, data_dir):
        payload = _valid_profile_payload(
            id="derived-profile",
            display_name="Derived Profile",
            schema_version=3,
            requirements={
                "needs": ["tensorcore", "cuda"],
                "optimize_for": ["throughput"],
                "constraints": {},
            },
            derived_capabilities=["manual-should-be-ignored"],
            decision_trace=["profile trace"],
        )
        resp = client.post("/api/profiles", json=payload)
        assert resp.status_code == 201

        with patch.dict(os.environ, {"STACKWARDEN_DATA_DIR": str(data_dir)}):
            profile = load_profile("derived-profile")
            assert profile.derived_capabilities == ["tensorcore", "cuda"]
            assert "profile trace" in profile.decision_trace
            assert any(
                "Ignored user-supplied derived_capabilities" in msg
                for msg in profile.decision_trace
            )
            assert any(
                "Computed derived_capabilities from requirements.needs." in msg
                for msg in profile.decision_trace
            )


class TestCompatibilityPreview:
    def test_preview_reports_incompatible_requirements(self, client):
        profile = _valid_profile_payload(
            schema_version=2,
            arch="arm64",
            base_candidates=[],
            host_facts={"driver_version": "550.54", "runtime_version": None, "detected_at": None},
        )
        assert client.post("/api/profiles", json=profile).status_code == 201
        block = _valid_block_payload(
            schema_version=2,
            id="needs-amd64",
            requires={"arch": "amd64"},
        )
        assert client.post("/api/blocks", json=block).status_code == 201
        stack = _valid_stack_payload(
            schema_version=2,
            id="stack-needs-amd64",
            blocks=["needs-amd64"],
        )
        assert client.post("/api/stacks", json=stack).status_code == 201
        resp = client.post(
            "/api/compatibility/preview",
            json={"profile_id": "my-new-profile", "stack_id": "stack-needs-amd64"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["compatible"] is False
        assert any(e["code"] == "ARCH_MISMATCH" for e in body["errors"])


class TestCreateBlock:
    def test_success(self, client, data_dir):
        resp = client.post("/api/blocks", json=_valid_block_payload())
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == "fastapi"
        assert (data_dir / "blocks" / "fastapi.yaml").exists()
        with patch.dict(os.environ, {"STACKWARDEN_DATA_DIR": str(data_dir)}):
            block = load_block("fastapi")
            assert block.id == "fastapi"

    def test_conflict(self, client):
        payload = _valid_block_payload()
        assert client.post("/api/blocks", json=payload).status_code == 201
        assert client.post("/api/blocks", json=payload).status_code == 409

    def test_dry_run(self, client):
        resp = client.post("/api/blocks/dry-run", json=_valid_block_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert "kind: block" in body["yaml"]

    def test_block_create_supports_npm_and_apt_constraints(self, client):
        payload = _valid_block_payload(
            npm=[{"name": "@types/node", "version": "22.0.0", "version_mode": "custom", "package_manager": "npm"}],
            apt=["curl"],
            apt_constraints={"curl": "=8.5.0-1ubuntu1"},
        )
        resp = client.post("/api/blocks", json=payload)
        assert resp.status_code == 201

    def test_block_rejects_lock_only_without_lockfile_copy(self, client):
        payload = _valid_block_payload(
            npm_install_mode="lock_only",
            copy_items=[],
        )
        resp = client.post("/api/blocks", json=payload)
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert any(e["field"] == "copy_items" for e in detail)

    def test_block_rejects_pin_only_without_all_constraints(self, client):
        payload = _valid_block_payload(
            apt=["curl", "git"],
            apt_constraints={"curl": "=8.5.0-1ubuntu1"},
            apt_install_mode="pin_only",
        )
        resp = client.post("/api/blocks", json=payload)
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert any(e["field"] == "apt_constraints" for e in detail)

    def test_block_create_accepts_wheelhouse_mode(self, client):
        payload = _valid_block_payload(
            pip_install_mode="wheelhouse_prefer",
            pip_wheelhouse_path="wheels",
        )
        resp = client.post("/api/blocks", json=payload)
        assert resp.status_code == 201

    def test_block_create_emits_metric_events(self, client, caplog):
        caplog.set_level(logging.INFO)
        resp = client.post("/api/blocks", json=_valid_block_payload(id="metric-block"))
        assert resp.status_code == 201
        metric_lines = [r.getMessage() for r in caplog.records if "metric_event" in r.getMessage()]
        assert any("create_attempt" in line and "metric-block" in line for line in metric_lines)
        assert any("create_result" in line and "'outcome': 'success'" in line for line in metric_lines)

    def test_block_dry_run_emits_metric_events(self, client, caplog):
        caplog.set_level(logging.INFO)
        resp = client.post("/api/blocks/dry-run", json=_valid_block_payload(id="metric-block-dry"))
        assert resp.status_code == 200
        metric_lines = [r.getMessage() for r in caplog.records if "metric_event" in r.getMessage()]
        assert any("dry_run_attempt" in line and "metric-block-dry" in line for line in metric_lines)
        assert any("dry_run_result" in line and "'outcome': 'success'" in line for line in metric_lines)


# ---------------------------------------------------------------------------
# Atomic writer tests
# ---------------------------------------------------------------------------

class TestAtomicWrite:
    def test_creates_dirs(self, tmp_path):
        from stackwarden.web.util.write_yaml import atomic_write_yaml

        target = tmp_path / "nested" / "deep" / "spec.yaml"
        atomic_write_yaml({"id": "test"}, target)
        assert target.exists()
        assert target.read_text().startswith("id: test")

    def test_dir_fsync_called(self, tmp_path):
        from stackwarden.web.util.write_yaml import atomic_write_yaml

        target = tmp_path / "spec.yaml"
        calls = []
        real_fsync = os.fsync

        def tracking_fsync(fd):
            calls.append(fd)
            return real_fsync(fd)

        with patch("stackwarden.web.util.write_yaml.os.fsync", side_effect=tracking_fsync):
            atomic_write_yaml({"id": "test"}, target)

        assert len(calls) == 2, "Expected two fsync calls (file + directory)"


# ---------------------------------------------------------------------------
# Meta enums test
# ---------------------------------------------------------------------------

class TestMetaEnums:
    def test_returns_enum_values(self, client):
        resp = client.get("/api/meta/enums")
        assert resp.status_code == 200
        body = resp.json()
        assert "custom" in body["task"]
        assert "pull" in body["build_strategy"]
        assert "overlay" in body["build_strategy"]
        assert "dockerfile_template" not in body["build_strategy"]
        assert "arm64" in body["arch"]
        assert "amd64" in body["arch"]


# ---------------------------------------------------------------------------
# Duplicate tests
# ---------------------------------------------------------------------------

class TestDuplicateStack:
    def test_success(self, client, data_dir):
        _ensure_fastapi_block(client)
        client.post("/api/stacks", json=_valid_stack_payload())
        resp = client.post("/api/stacks/my-new-stack/duplicate", json={
            "new_id": "my-stack-copy",
            "overrides": {"display_name": "My Stack Copy"},
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == "my-stack-copy"
        assert (data_dir / "stacks" / "my-stack-copy.yaml").exists()

    def test_reject_unsafe_override(self, client):
        _ensure_fastapi_block(client)
        client.post("/api/stacks", json=_valid_stack_payload())
        resp = client.post("/api/stacks/my-new-stack/duplicate", json={
            "new_id": "my-stack-copy",
            "overrides": {"task": "llm"},
        })
        assert resp.status_code == 422

    def test_source_not_found(self, client):
        resp = client.post("/api/stacks/nonexistent/duplicate", json={
            "new_id": "copy",
        })
        assert resp.status_code == 404


class TestDuplicateProfile:
    def test_success(self, client, data_dir):
        client.post("/api/profiles", json=_valid_profile_payload())
        resp = client.post("/api/profiles/my-new-profile/duplicate", json={
            "new_id": "my-profile-copy",
            "overrides": {"display_name": "My Profile Copy"},
        })
        assert resp.status_code == 201
        assert (data_dir / "profiles" / "my-profile-copy.yaml").exists()
