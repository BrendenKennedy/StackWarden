from __future__ import annotations

import types

import pytest

from stackwarden.ui.wizard_entities.block import run_block_create_wizard, run_layer_create_wizard
from stackwarden.ui.wizard_entities.profile import run_profile_create_wizard
from stackwarden.ui.wizard_entities.stack import run_stack_create_wizard


def test_profile_wizard_noninteractive_dry_run(monkeypatch):
    hints = types.SimpleNamespace(
        arch="amd64",
        container_runtime="nvidia",
        resolved_ids={"os_family_id": "ubuntu", "os_version_id": "ubuntu_22_04", "gpu_vendor_id": "nvidia", "gpu_family_id": "ampere"},
        gpu=types.SimpleNamespace(compute_capability="8.0"),
        cuda=types.SimpleNamespace(major=12, minor=2, variant="runtime"),
        gpu_devices=[],
    )
    monkeypatch.setattr("stackwarden.ui.wizard_entities.profile.detect_server_hints", lambda: hints)
    result = run_profile_create_wizard(
        profile_id="test_profile",
        display_name="Test Profile",
        arch="amd64",
        container_runtime="nvidia",
        non_interactive=True,
        dry_run=True,
        yes=True,
    )
    assert result.valid is True
    assert result.created is False
    assert "id: test_profile" in result.yaml


def test_layer_wizard_noninteractive_with_preset(monkeypatch):
    result = run_layer_create_wizard(
        layer_id="test_layer",
        display_name="Test Layer",
        preset_id="vllm_model_runtime",
        non_interactive=True,
        dry_run=True,
        yes=True,
    )
    assert result.valid is True
    assert result.created is False
    assert "id: test_layer" in result.yaml


def test_block_wizard_alias_warns_and_delegates(monkeypatch):
    with pytest.warns(
        DeprecationWarning,
        match="run_block_create_wizard is deprecated.*2026-06-30",
    ):
        result = run_block_create_wizard(
            block_id="legacy_block",
            display_name="Legacy Layer",
            preset_id="vllm_model_runtime",
            non_interactive=True,
            dry_run=True,
            yes=True,
        )
    assert result.valid is True


def test_stack_wizard_requires_runtime_layer(monkeypatch):
    monkeypatch.setattr("stackwarden.ui.wizard_entities.stack.list_profile_ids", lambda: ["p1"])
    monkeypatch.setattr(
        "stackwarden.ui.wizard_entities.stack.load_profile",
        lambda _id: types.SimpleNamespace(id=_id),
    )
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.load_profile",
        lambda _id: types.SimpleNamespace(id=_id, host_facts=types.SimpleNamespace(confidence={})),
    )
    monkeypatch.setattr(
        "stackwarden.ui.wizard_entities.stack.classify_layer_options",
        lambda **_kwargs: [],
    )
    monkeypatch.setattr("stackwarden.ui.wizard_entities.stack.list_layer_ids", lambda: ["app_only"])
    monkeypatch.setattr(
        "stackwarden.ui.wizard_entities.stack.load_layer",
        lambda _id: types.SimpleNamespace(id=_id, tags=["api"], stack_layer="application_orchestration_layer"),
    )
    with pytest.raises(ValueError, match="Missing required layer groups"):
        run_stack_create_wizard(
            stack_id="test_stack",
            display_name="Test Stack",
            layers=["app_only"],
            non_interactive=True,
            dry_run=True,
            yes=True,
        )


def test_stack_wizard_uses_classified_layer_defaults(monkeypatch):
    monkeypatch.setattr("stackwarden.ui.wizard_entities.stack.list_profile_ids", lambda: ["p1"])
    monkeypatch.setattr(
        "stackwarden.ui.wizard_entities.stack.load_profile",
        lambda _id: types.SimpleNamespace(id=_id),
    )
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.load_profile",
        lambda _id: types.SimpleNamespace(id=_id, host_facts=types.SimpleNamespace(confidence={})),
    )
    monkeypatch.setattr(
        "stackwarden.ui.wizard_entities.stack.list_layer_ids",
        lambda: ["runtime_base", "engine_core", "serve_api"],
    )
    by_id = {
        "runtime_base": types.SimpleNamespace(id="runtime_base", tags=["runtime"], stack_layer="system_runtime_layer"),
        "engine_core": types.SimpleNamespace(id="engine_core", tags=["llm"], stack_layer="inference_engine_layer"),
        "serve_api": types.SimpleNamespace(id="serve_api", tags=["serving"], stack_layer="serving_layer"),
    }
    monkeypatch.setattr("stackwarden.ui.wizard_entities.stack.load_layer", lambda layer_id: by_id[layer_id])

    def _classified(**_kwargs):
        return [
            types.SimpleNamespace(
                stack_layer="system_runtime_layer",
                options=[types.SimpleNamespace(id="runtime_base", tier="recommended", reasons=[])],
            ),
            types.SimpleNamespace(
                stack_layer="inference_engine_layer",
                options=[types.SimpleNamespace(id="engine_core", tier="recommended", reasons=[])],
            ),
            types.SimpleNamespace(
                stack_layer="serving_layer",
                options=[types.SimpleNamespace(id="serve_api", tier="recommended", reasons=[])],
            ),
        ]

    monkeypatch.setattr("stackwarden.ui.wizard_entities.stack.classify_layer_options", _classified)
    monkeypatch.setattr(
        "stackwarden.ui.wizard_entities.stack.compose_stack_preview",
        lambda _req: types.SimpleNamespace(
            valid=True,
            errors=[],
            dependency_conflicts=[],
            tuple_conflicts=[],
            runtime_conflicts=[],
        ),
    )
    monkeypatch.setattr(
        "stackwarden.ui.wizard_entities.stack.dry_run_stack",
        lambda req: types.SimpleNamespace(valid=True, yaml=f"id: {req.id}\nlayers:\n- runtime_base\n- engine_core\n- serve_api\n", errors=[]),
    )

    result = run_stack_create_wizard(
        stack_id="intent_stack",
        display_name="Intent Stack",
        non_interactive=True,
        dry_run=True,
        yes=True,
    )

    assert result.valid is True
    assert "- runtime_base" in result.yaml
    assert "- engine_core" in result.yaml
    assert "- serve_api" in result.yaml
