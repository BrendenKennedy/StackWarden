"""Stress tests: wheelhouse and npm.

- Wheelhouse missing when wheelhouse_only — build fails with clear error
- Lockfile vs spec: lock_prefer uses lock when present, falls back to spec
- npm + pip in same stack — both applied correctly
"""

from __future__ import annotations

import pytest

from stacksmith.builders.overlay import _resolve_npm_install_commands
from stacksmith.domain.hashing import fingerprint
from stacksmith.domain.models import (
    BaseCandidate,
    CudaSpec,
    GpuSpec,
    PipDep,
    Profile,
    StackComponents,
    StackEntrypoint,
    StackSpec,
)


def _profile() -> Profile:
    return Profile.model_validate(dict(
        id="p1",
        display_name="P1",
        arch="amd64",
        cuda=CudaSpec(major=0, minor=0, variant="none"),
        gpu=GpuSpec(vendor="none", family="none"),
        base_candidates=[BaseCandidate(name="python", tags=["3.12-slim"])],
    ))


def _stack(**kw) -> StackSpec:
    base = dict(
        id="s1",
        display_name="S1",
        task="custom",
        serve="python_api",
        api="fastapi",
        build_strategy="overlay",
        components=StackComponents(base_role="python"),
        entrypoint=StackEntrypoint(cmd=["python", "-m", "uvicorn"]),
    )
    base.update(kw)
    return StackSpec.model_validate(base)


class TestWheelhouseMissing:
    """wheelhouse_only with missing path fails with clear error."""

    def test_wheelhouse_only_requires_path(self):
        """Stack with wheelhouse_only but empty path should fail validation."""
        from stacksmith.domain.models import StackSpec

        data = {
            "id": "s1", "display_name": "S1", "task": "custom", "serve": "custom", "api": "none",
            "build_strategy": "overlay",
            "components": {
                "base_role": "python",
                "pip_install_mode": "wheelhouse_only",
                "pip_wheelhouse_path": "",
            },
            "entrypoint": {"cmd": ["python", "-V"]},
        }
        with pytest.raises(ValueError):
            StackSpec.model_validate(data)

    def test_wheelhouse_path_affects_fingerprint(self):
        """Different wheelhouse paths produce different fingerprints."""
        p = _profile()
        s1 = _stack(components=StackComponents(
            base_role="python",
            pip_install_mode="wheelhouse_only",
            pip_wheelhouse_path="wheels/a",
        ))
        s2 = _stack(components=StackComponents(
            base_role="python",
            pip_install_mode="wheelhouse_only",
            pip_wheelhouse_path="wheels/b",
        ))
        fp1 = fingerprint(p, s1, "base:latest")
        fp2 = fingerprint(p, s2, "base:latest")
        assert fp1 != fp2


class TestNpmLockPrefer:
    """lock_prefer uses lockfile when present, falls back to spec."""

    def test_lock_prefer_with_lockfile_uses_npm_ci(self):
        s = _stack(
            components={
                "base_role": "python",
                "npm_install_mode": "lock_prefer",
                "npm": [{"name": "next", "version_mode": "latest", "package_manager": "npm"}],
            },
            files={"copy": [{"src": "apps/web/package-lock.json", "dst": "/app/package-lock.json"}]},
        )
        cmds = _resolve_npm_install_commands(s)
        assert cmds == ["npm ci --no-audit --no-fund"]

    def test_lock_prefer_without_lockfile_falls_back(self):
        s = _stack(
            components={
                "base_role": "python",
                "npm_install_mode": "lock_prefer",
                "npm": [{"name": "next", "version_mode": "latest", "package_manager": "npm"}],
            },
        )
        cmds = _resolve_npm_install_commands(s)
        assert len(cmds) == 1
        assert "npm install" in cmds[0]


class TestNpmAndPip:
    """Stack with both npm and pip deps."""

    def test_both_modes_affect_fingerprint(self):
        p = _profile()
        s1 = _stack(components=StackComponents(
            base_role="python",
            pip=[PipDep(name="fastapi", version=">=0.1")],
            npm_install_mode="spec",
        ))
        s2 = _stack(components=StackComponents(
            base_role="python",
            pip=[PipDep(name="fastapi", version=">=0.1")],
            npm=[{"name": "next", "version_mode": "latest", "package_manager": "npm"}],
            npm_install_mode="spec",
        ))
        fp1 = fingerprint(p, s1, "base:latest")
        fp2 = fingerprint(p, s2, "base:latest")
        assert fp1 != fp2
