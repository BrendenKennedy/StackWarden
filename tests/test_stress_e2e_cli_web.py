"""End-to-end stress tests across CLI and web API surfaces.

These tests focus on repeated, cross-surface behavior:
- plan determinism between CLI and API across many runs
- ensure flag bundle robustness for API job creation
- ensure flag bundle propagation from CLI to ensure_internal
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from stackwarden.cli import app as cli_app


def _stress_loops(default: int = 20) -> int:
    raw = os.environ.get("STACKWARDEN_STRESS_LOOPS", "")
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, min(value, 200))


def _extract_json(output: str) -> dict:
    text = output.strip()
    decoder = json.JSONDecoder()
    parsed: dict | None = None
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, end = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if text[idx + end :].strip():
            continue
        if isinstance(obj, dict):
            parsed = obj
    if parsed is None:
        raise AssertionError(f"Expected JSON output, got: {output!r}")
    return parsed


def _invoke_cli_json(runner: CliRunner, args: list[str]) -> dict:
    result = runner.invoke(cli_app, args)
    assert result.exit_code == 0, result.output
    return _extract_json(result.output)


def _profile_payload(profile_id: str) -> dict:
    return {
        "id": profile_id,
        "display_name": "Stress Profile",
        "arch": "amd64",
        "os": "linux",
        "container_runtime": "runc",
        "cuda": None,
        "gpu": {"vendor": "none", "family": "none"},
        "capabilities": [],
        "base_candidates": [
            {"name": "docker.io/library/python", "tags": ["3.12-slim"], "score_bias": 0},
        ],
        "defaults": {"python": "3.12", "user": "root", "workdir": "/workspace"},
    }


def _block_payload(block_id: str) -> dict:
    return {
        "id": block_id,
        "display_name": "Stress Block",
        "stack_layer": "application_orchestration_layer",
        "tags": ["stress"],
        "build_strategy": "overlay",
        "base_role": "python",
        "pip": [{"name": "six", "version": ">=1.16"}],
        "pip_install_mode": "index",
        "pip_wheelhouse_path": "",
        "npm": [],
        "apt": [],
        "apt_constraints": {},
        "env": {},
        "ports": [],
        "entrypoint_cmd": ["python", "-c", "print('ok')"],
        "copy_items": [],
        "variants": {},
    }


def _stack_payload(stack_id: str, block_id: str) -> dict:
    return {
        "kind": "stack_recipe",
        "id": stack_id,
        "display_name": "Stress Stack",
        "build_strategy": "overlay",
        "base_role": "python",
        "blocks": [block_id],
        "copy_items": [],
        "variants": {},
    }


@pytest.fixture()
def stress_client(tmp_path):
    for name in ("stacks", "profiles", "blocks"):
        (tmp_path / name).mkdir()
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
        yield TestClient(app), tmp_path


def test_plan_deterministic_between_cli_and_api_under_repetition(stress_client):
    client, _tmp_path = stress_client
    profile_id = "stress_profile_e2e"
    block_id = "stress_block_e2e"
    stack_id = "stress_stack_e2e"

    assert client.post("/api/profiles", json=_profile_payload(profile_id)).status_code == 201
    assert client.post("/api/layers", json=_block_payload(block_id)).status_code == 201
    assert client.post("/api/stacks", json=_stack_payload(stack_id, block_id)).status_code == 201

    runner = CliRunner()
    loops = _stress_loops(default=25)
    fingerprints: set[str] = set()

    for _ in range(loops):
        cli_body = _invoke_cli_json(
            runner,
            ["plan", "--profile", profile_id, "--stack", stack_id, "--json"],
        )

        api_res = client.post(
            "/api/plan",
            json={"profile_id": profile_id, "stack_id": stack_id, "variants": {}, "flags": {}},
        )
        assert api_res.status_code == 200, api_res.text
        api_body = api_res.json()

        assert cli_body["decision"]["base_image"] == api_body["base_image"]
        assert cli_body["decision"]["builder"] == api_body["builder"]
        assert cli_body["artifact"]["fingerprint"] == api_body["fingerprint"]
        fingerprints.add(api_body["fingerprint"])

    # Repeated runs should remain deterministic for unchanged inputs.
    assert len(fingerprints) == 1


def test_ensure_flag_bundles_are_robust_for_api_and_cli(stress_client, monkeypatch):
    client, _tmp_path = stress_client
    profile_id = "stress_profile_flags"
    block_id = "stress_block_flags"
    stack_id = "stress_stack_flags"

    assert client.post("/api/profiles", json=_profile_payload(profile_id)).status_code == 201
    assert client.post("/api/layers", json=_block_payload(block_id)).status_code == 201
    assert client.post("/api/stacks", json=_stack_payload(stack_id, block_id)).status_code == 201

    # Keep API ensure cheap while still exercising request validation + job creation.
    monkeypatch.setattr(
        "stackwarden.web.routes.jobs.resolve",
        lambda *args, **kwargs: SimpleNamespace(decision=SimpleNamespace(build_optimization=None)),
    )
    monkeypatch.setattr(
        "stackwarden.web.routes.jobs.decide_admission",
        lambda **_kwargs: SimpleNamespace(allowed=True, detail="ok"),
    )

    async def _fake_run_ensure_job(*_args, **_kwargs):
        return None

    monkeypatch.setattr("stackwarden.web.routes.jobs.run_ensure_job", _fake_run_ensure_job)

    bundles = [
        {},
        {"rebuild": True},
        {"immutable": True},
        {"upgrade_base": True},
        {"no_hooks": True},
        {"explain": True},
        {"rebuild": True, "upgrade_base": True, "no_hooks": True, "explain": True},
        {"immutable": True, "rebuild": True},
    ]
    loops = _stress_loops(default=30)

    for i in range(loops):
        bundle = bundles[i % len(bundles)]
        resp = client.post(
            "/api/ensure",
            json={"profile_id": profile_id, "stack_id": stack_id, "variants": {}, "flags": bundle},
        )
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["job_id"]

        detail = client.get(f"/api/jobs/{job_id}")
        assert detail.status_code == 200
        assert detail.json()["flags"] == bundle

    # Also verify CLI flag bundles map correctly into ensure_internal kwargs.
    runner = CliRunner()
    captured: list[dict] = []

    def _fake_ensure_internal(*_args, **kwargs):
        captured.append(kwargs)
        record = SimpleNamespace(
            model_dump=lambda **_k: {"tag": "local/stackwarden:stress", "status": "built"},
            tag="local/stackwarden:stress",
            status=SimpleNamespace(value="built"),
            image_id=None,
            digest=None,
        )
        result = SimpleNamespace(decision=SimpleNamespace(rationale=None))
        return record, result

    with patch("stackwarden.domain.ensure.ensure_internal", side_effect=_fake_ensure_internal):
        for bundle in bundles:
            args = ["ensure", "--profile", profile_id, "--stack", stack_id, "--json"]
            if bundle.get("rebuild"):
                args.append("--rebuild")
            if bundle.get("upgrade_base"):
                args.append("--upgrade-base")
            if bundle.get("immutable"):
                args.append("--immutable")
            if bundle.get("no_hooks"):
                args.append("--no-hooks")
            if bundle.get("explain"):
                args.append("--explain")

            body = _invoke_cli_json(runner, args)
            assert body["tag"] == "local/stackwarden:stress"

    assert len(captured) == len(bundles)
    for bundle, kwargs in zip(bundles, captured):
        assert kwargs["rebuild"] == bundle.get("rebuild", False)
        assert kwargs["upgrade_base"] == bundle.get("upgrade_base", False)
        assert kwargs["immutable"] == bundle.get("immutable", False)
        assert kwargs["run_hooks"] == (not bundle.get("no_hooks", False))
        assert kwargs["explain"] == bundle.get("explain", False)


def test_cli_json_output_is_parseable_under_stress_noise(stress_client):
    client, _tmp_path = stress_client
    profile_id = "stress_profile_json"
    block_id = "stress_block_json"
    stack_id = "stress_stack_json"

    assert client.post("/api/profiles", json=_profile_payload(profile_id)).status_code == 201
    assert client.post("/api/layers", json=_block_payload(block_id)).status_code == 201
    assert client.post("/api/stacks", json=_stack_payload(stack_id, block_id)).status_code == 201

    runner = CliRunner()
    body = _invoke_cli_json(
        runner,
        ["plan", "--profile", profile_id, "--stack", stack_id, "--json"],
    )
    assert body["profile_id"] == profile_id
    assert body["stack_id"] == stack_id
