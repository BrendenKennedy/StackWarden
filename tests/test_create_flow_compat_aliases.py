from __future__ import annotations

from pathlib import Path

import pytest

from stackwarden.application import create_flows


def test_create_block_alias_warns_and_delegates(monkeypatch):
    expected = Path("/tmp/layer.yaml")
    monkeypatch.setattr(create_flows, "create_layer", lambda req: expected)
    with pytest.warns(
        DeprecationWarning,
        match=f"create_block is deprecated.*{create_flows.BLOCK_ALIAS_REMOVE_AFTER}",
    ):
        result = create_flows.create_block(object())  # type: ignore[arg-type]
    assert result == expected


def test_update_block_alias_warns_and_delegates(monkeypatch):
    expected = Path("/tmp/layer.yaml")
    monkeypatch.setattr(create_flows, "update_layer", lambda layer_id, req: expected)
    with pytest.warns(
        DeprecationWarning,
        match=f"update_block is deprecated.*{create_flows.BLOCK_ALIAS_REMOVE_AFTER}",
    ):
        result = create_flows.update_block("legacy-block", object())  # type: ignore[arg-type]
    assert result == expected


def test_dry_run_block_alias_warns_and_delegates(monkeypatch):
    expected = create_flows.DryRunResult(valid=True, errors=[], yaml="")
    monkeypatch.setattr(create_flows, "dry_run_layer", lambda req: expected)
    with pytest.warns(
        DeprecationWarning,
        match=f"dry_run_block is deprecated.*{create_flows.BLOCK_ALIAS_REMOVE_AFTER}",
    ):
        result = create_flows.dry_run_block(object())  # type: ignore[arg-type]
    assert result == expected
