"""Tests for block-based stack composition."""

from __future__ import annotations

import pytest

from stackwarden.domain.composition import analyze_recipe_tuple_conflicts, compose_stack
from stackwarden.domain.models import BlockSpec, StackRecipeSpec


def _block(**overrides) -> BlockSpec:
    base = {
        "kind": "block",
        "id": "base",
        "display_name": "Base",
    }
    base.update(overrides)
    return BlockSpec.model_validate(base)


def _recipe(**overrides) -> StackRecipeSpec:
    base = {
        "kind": "stack_recipe",
        "id": "svc",
        "display_name": "Service",
        "task": "custom",
        "serve": "python_api",
        "api": "fastapi",
        "blocks": ["base"],
    }
    base.update(overrides)
    return StackRecipeSpec.model_validate(base)


def test_compose_basic_merge():
    recipe = _recipe(
        blocks=["runtime", "api"],
        components={"pip": [{"name": "uvicorn", "version": "==0.30.*"}]},
        env=["APP_MODE=prod"],
    )
    runtime = _block(
        id="runtime",
        components={
            "base_role": "pytorch",
            "pip": [{"name": "torch", "version": "==2.4.0"}],
            "npm": [{"name": "next", "version": "^15.0.0", "version_mode": "custom"}],
            "apt": ["curl"],
            "apt_constraints": {"curl": "=8.5.0-1ubuntu1"},
        },
        build_strategy="overlay",
        entrypoint={"cmd": ["python", "-m", "uvicorn", "app.main:app"]},
        env=["APP_MODE=dev", "PYTHONUNBUFFERED=1"],
        ports=[8000],
    )
    api = _block(
        id="api",
        components={
            "pip": [{"name": "fastapi", "version": "==0.115.*"}],
            "npm": [{"name": "next", "version_mode": "latest"}],
        },
        env=["APP_MODE=stage"],
        ports=[8080],
    )

    composed = compose_stack(recipe, [runtime, api])

    assert composed.id == "svc"
    assert composed.task.value == "custom"
    assert composed.components.base_role == "pytorch"
    assert [p.name for p in composed.components.pip] == ["fastapi", "torch", "uvicorn"]
    assert len(composed.components.npm) == 1
    assert composed.components.npm[0].name == "next"
    assert composed.components.npm[0].version_mode == "latest"
    assert composed.components.apt_constraints == {"curl": "=8.5.0-1ubuntu1"}
    assert composed.env == ["APP_MODE=prod", "PYTHONUNBUFFERED=1"]
    assert composed.ports == [8000, 8080]


def test_compose_detects_missing_block():
    recipe = _recipe(blocks=["missing"])
    with pytest.raises(ValueError):
        compose_stack(recipe, [])


def test_compose_detects_duplicate_block_reference():
    recipe = _recipe(blocks=["a", "a"])
    a = _block(
        id="a",
        components={"base_role": "pytorch"},
        build_strategy="overlay",
        entrypoint={"cmd": ["python", "main.py"]},
    )
    with pytest.raises(ValueError):
        compose_stack(recipe, [a])


def test_compose_detects_incompatible_pinned_versions():
    recipe = _recipe(blocks=["a", "b"])
    a = _block(
        id="a",
        components={"base_role": "pytorch", "pip": [{"name": "numpy", "version": "==1.26.0"}]},
        build_strategy="overlay",
        entrypoint={"cmd": ["python", "main.py"]},
    )
    b = _block(id="b", components={"pip": [{"name": "numpy", "version": "==2.0.0"}]})
    with pytest.raises(ValueError):
        compose_stack(recipe, [a, b])


def test_compose_applies_defaults_for_missing_runtime_fields():
    recipe = _recipe(blocks=["only"], components={"base_role": "pytorch"})
    only = _block(id="only")
    composed = compose_stack(recipe, [only])
    assert composed.components.base_role == "pytorch"
    assert composed.build_strategy.value == "overlay"
    assert composed.entrypoint.cmd == ["python", "-c", "import time; time.sleep(3600)"]


def test_compose_applies_recipe_wheelhouse_override():
    recipe = _recipe(
        blocks=["runtime"],
        components={
            "pip_install_mode": "wheelhouse_only",
            "pip_wheelhouse_path": "wheels/release",
        },
    )
    runtime = _block(
        id="runtime",
        components={
            "base_role": "pytorch",
            "pip_install_mode": "wheelhouse_prefer",
            "pip_wheelhouse_path": "wheels/dev",
        },
        build_strategy="overlay",
        entrypoint={"cmd": ["python", "main.py"]},
    )
    composed = compose_stack(recipe, [runtime])
    assert composed.components.pip_install_mode == "wheelhouse_only"
    assert composed.components.pip_wheelhouse_path == "wheels/release"


def test_tuple_conflicts_detected_for_conflicting_requires():
    recipe = _recipe(blocks=["a", "b"])
    a = _block(id="a", requires={"arch": "amd64"})
    b = _block(id="b", requires={"arch": "arm64"})
    conflicts = analyze_recipe_tuple_conflicts(recipe, [a, b])
    assert any(c["type"] == "tuple" and c["name"] == "arch" for c in conflicts)

