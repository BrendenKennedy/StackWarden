from __future__ import annotations

import types

import pytest

from stackwarden.ui.wizard_entities.block import run_block_create_wizard
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


def test_block_wizard_noninteractive_with_preset(monkeypatch):
    result = run_block_create_wizard(
        block_id="test_block",
        display_name="Test Block",
        preset_id="vllm",
        non_interactive=True,
        dry_run=True,
        yes=True,
    )
    assert result.valid is True
    assert result.created is False
    assert "id: test_block" in result.yaml


def test_stack_wizard_requires_runtime_layer(monkeypatch):
    monkeypatch.setattr("stackwarden.ui.wizard_entities.stack.list_profile_ids", lambda: [])
    monkeypatch.setattr("stackwarden.ui.wizard_entities.stack.list_block_ids", lambda: ["app_only"])
    monkeypatch.setattr(
        "stackwarden.ui.wizard_entities.stack.load_block",
        lambda _id: types.SimpleNamespace(id=_id, tags=["api"]),
    )
    with pytest.raises(ValueError, match="system/runtime layer"):
        run_stack_create_wizard(
            stack_id="test_stack",
            display_name="Test Stack",
            blocks=["app_only"],
            non_interactive=True,
            dry_run=True,
            yes=True,
        )
