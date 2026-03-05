"""Tests for overlay npm install policy command resolution."""

from stacksmith.builders.overlay import _resolve_npm_install_commands
from stacksmith.domain.models import StackSpec


def _make_stack(**overrides) -> StackSpec:
    base = {
        "id": "overlay-policy",
        "display_name": "Overlay Policy",
        "task": "custom",
        "serve": "python_api",
        "api": "fastapi",
        "build_strategy": "overlay",
        "components": {
            "base_role": "pytorch",
            "npm": [{"name": "next", "version_mode": "latest", "package_manager": "npm"}],
            "npm_install_mode": "spec",
        },
        "entrypoint": {"cmd": ["python", "-m", "uvicorn"]},
        "files": {"copy": []},
    }
    base.update(overrides)
    return StackSpec.model_validate(base)


def test_spec_mode_uses_declared_npm_deps():
    stack = _make_stack()
    cmds = _resolve_npm_install_commands(stack)
    assert len(cmds) == 1
    assert cmds[0].startswith("npm install --no-audit --no-fund")


def test_lock_prefer_uses_lockfile_when_present():
    stack = _make_stack(
        components={
            "base_role": "pytorch",
            "npm_install_mode": "lock_prefer",
            "npm": [{"name": "next", "version_mode": "latest", "package_manager": "npm"}],
        },
        files={"copy": [{"src": "apps/web/package-lock.json", "dst": "/app/package-lock.json"}]},
    )
    assert _resolve_npm_install_commands(stack) == ["npm ci --no-audit --no-fund"]


def test_lock_prefer_falls_back_to_spec_when_lockfile_missing():
    stack = _make_stack(
        components={
            "base_role": "pytorch",
            "npm_install_mode": "lock_prefer",
            "npm": [{"name": "next", "version_mode": "latest", "package_manager": "npm"}],
        },
    )
    cmds = _resolve_npm_install_commands(stack)
    assert len(cmds) == 1
    assert cmds[0].startswith("npm install --no-audit --no-fund")
