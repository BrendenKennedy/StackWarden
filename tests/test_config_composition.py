"""Tests for config loaders with composed stack recipes."""

from __future__ import annotations

import yaml

from stacksmith.config import load_block, load_stack
from stacksmith.domain.errors import BlockNotFoundError, StacksmithError


def _write_yaml(path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_load_stack_legacy_without_kind(monkeypatch, tmp_path):
    monkeypatch.setenv("STACKSMITH_DATA_DIR", str(tmp_path))
    _write_yaml(
        tmp_path / "stacks" / "legacy.yaml",
        {
            "schema_version": 1,
            "id": "legacy",
            "display_name": "Legacy",
            "task": "custom",
            "serve": "python_api",
            "api": "fastapi",
            "build_strategy": "overlay",
            "components": {"base_role": "pytorch"},
            "entrypoint": {"cmd": ["python", "main.py"]},
        },
    )

    loaded = load_stack("legacy")
    assert loaded.id == "legacy"
    assert loaded.kind == "stack"


def test_load_stack_recipe_composes(monkeypatch, tmp_path):
    monkeypatch.setenv("STACKSMITH_DATA_DIR", str(tmp_path))
    _write_yaml(
        tmp_path / "blocks" / "runtime.yaml",
        {
            "kind": "block",
            "schema_version": 1,
            "id": "runtime",
            "display_name": "Runtime",
            "build_strategy": "overlay",
            "components": {"base_role": "pytorch", "pip": [{"name": "torch", "version": "==2.4.0"}]},
            "entrypoint": {"cmd": ["python", "main.py"]},
        },
    )
    _write_yaml(
        tmp_path / "stacks" / "recipe.yaml",
        {
            "kind": "stack_recipe",
            "schema_version": 1,
            "id": "recipe",
            "display_name": "Recipe",
            "task": "custom",
            "serve": "python_api",
            "api": "fastapi",
            "blocks": ["runtime"],
        },
    )

    loaded = load_stack("recipe")
    assert loaded.id == "recipe"
    assert loaded.components.base_role == "pytorch"
    assert loaded.entrypoint.cmd == ["python", "main.py"]


def test_load_stack_unknown_kind_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("STACKSMITH_DATA_DIR", str(tmp_path))
    _write_yaml(
        tmp_path / "stacks" / "bad_kind.yaml",
        {
            "kind": "mystery",
            "id": "bad_kind",
            "display_name": "Bad",
        },
    )

    try:
        load_stack("bad_kind")
        assert False, "expected StacksmithError"
    except StacksmithError as exc:
        assert "unknown kind" in str(exc)


def test_load_block_requires_kind(monkeypatch, tmp_path):
    monkeypatch.setenv("STACKSMITH_DATA_DIR", str(tmp_path))
    _write_yaml(
        tmp_path / "blocks" / "bad_block.yaml",
        {
            "id": "bad_block",
            "display_name": "Bad Block",
        },
    )

    try:
        load_block("bad_block")
        assert False, "expected StacksmithError"
    except StacksmithError as exc:
        assert "missing kind" in str(exc)


def test_load_block_not_found(monkeypatch, tmp_path):
    monkeypatch.setenv("STACKSMITH_DATA_DIR", str(tmp_path))
    try:
        load_block("missing")
        assert False, "expected BlockNotFoundError"
    except BlockNotFoundError:
        pass

