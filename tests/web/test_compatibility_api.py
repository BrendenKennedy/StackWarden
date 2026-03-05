"""Compatibility preview API contract tests."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    (tmp_path / "stacks").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "blocks").mkdir()
    (tmp_path / "rules").mkdir()
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))

    (tmp_path / "rules" / "compatibility_rules.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "rules": [
                    {
                        "id": "runtime-hard",
                        "version": 1,
                        "strict_hard": True,
                        "when": {"gpu_vendor": "nvidia"},
                        "requires": {"container_runtime": "nvidia"},
                        "outcome": {
                            "code": "RUNTIME_MISMATCH",
                            "severity": "error",
                            "message": "Need nvidia runtime",
                        },
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    (tmp_path / "profiles" / "p1.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "id": "p1",
                "display_name": "P1",
                "arch": "amd64",
                "os": "linux",
                "container_runtime": "runc",
                "gpu": {"vendor": "nvidia", "family": "ampere"},
                "cuda": {"major": 12, "minor": 4, "variant": "cuda12.4"},
                "base_candidates": [{"name": "python", "tags": ["3.12-slim"]}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "stacks" / "s1.yaml").write_text(
        yaml.safe_dump(
            {
                "kind": "stack",
                "schema_version": 2,
                "id": "s1",
                "display_name": "S1",
                "task": "custom",
                "serve": "python_api",
                "api": "none",
                "build_strategy": "overlay",
                "components": {"base_role": "python", "pip": [], "apt": []},
                "entrypoint": {"cmd": ["python", "-V"]},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with patch.dict(
        os.environ,
        {
            "STACKWARDEN_DATA_DIR": str(tmp_path),
            "STACKWARDEN_WEB_DEV": "true",
            "STACKWARDEN_TUPLE_LAYER_MODE": "off",
        },
    ):
        from stackwarden.web.app import create_app
        from stackwarden.web.settings import WebSettings

        app = create_app(WebSettings(token=None, dev=True))
        yield TestClient(app)


def test_compatibility_preview_includes_rule_metadata(client):
    resp = client.post(
        "/api/compatibility/preview?strict=true",
        json={"profile_id": "p1", "stack_id": "s1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["compatible"] is False
    assert body["errors"][0]["code"] == "RUNTIME_MISMATCH"
    assert body["errors"][0]["rule_id"] == "runtime-hard"
    assert body["errors"][0]["rule_version"] == 1
    assert "requirements_summary" in body
    assert "effective_capabilities" in body["requirements_summary"]
    assert "tuple_decision" in body


def test_compatibility_preview_uses_env_strict_default(client, monkeypatch):
    captured: dict[str, bool] = {}

    monkeypatch.setattr("stackwarden.web.routes.compatibility.load_profile", lambda _id: object())
    monkeypatch.setattr("stackwarden.web.routes.compatibility.load_stack", lambda _id: type("S", (), {"blocks": []})())
    monkeypatch.setattr("stackwarden.web.routes.compatibility.load_block", lambda _id: object())

    def _fake_eval(_profile, _stack, *, blocks, strict_mode):
        captured["strict_mode"] = strict_mode
        return type("R", (), {"model_dump": lambda self, mode="json": {
            "compatible": True,
            "errors": [],
            "warnings": [],
            "info": [],
            "requirements_summary": {},
            "suggested_fixes": [],
            "decision_trace": [],
            "tuple_decision": {},
        }})()

    monkeypatch.setattr("stackwarden.web.routes.compatibility.evaluate_compatibility", _fake_eval)
    monkeypatch.setenv("STACKWARDEN_COMPAT_STRICT", "true")

    resp = client.post("/api/compatibility/preview", json={"profile_id": "p1", "stack_id": "s1"})
    assert resp.status_code == 200
    assert captured["strict_mode"] is True
