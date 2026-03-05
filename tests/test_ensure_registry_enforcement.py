from __future__ import annotations

from types import SimpleNamespace

import pytest

from stacksmith.config import AppConfig
from stacksmith.domain.errors import RegistryPolicyError
from stacksmith.domain.ensure import ensure_internal


def test_ensure_internal_enforces_registry_policy(monkeypatch):
    cfg = AppConfig(
        {
            "registry": {
                "allow": ["nvcr.io"],
                "deny": [],
            },
            "remote_catalog": {
                "enabled": False,
                "repo_url": None,
                "branch": "main",
                "local_path": "~/.local/share/stacksmith/remote-catalog",
                "auto_pull": True,
            },
        }
    )

    monkeypatch.setattr("stacksmith.config.AppConfig.load", lambda: cfg)
    monkeypatch.setattr("stacksmith.config.load_profile", lambda _profile_id: SimpleNamespace(id="p1"))
    monkeypatch.setattr("stacksmith.config.load_stack", lambda _stack_id: SimpleNamespace(id="s1", blocks=[]))
    monkeypatch.setattr("stacksmith.config.load_block", lambda _block_id: None)

    # Ensure we fail before catalog/build work if policy is violated.
    monkeypatch.setattr(
        "stacksmith.resolvers.resolver.resolve",
        lambda *_args, **_kwargs: SimpleNamespace(
            decision=SimpleNamespace(base_image="docker.io/library/ubuntu:22.04")
        ),
    )
    monkeypatch.setattr(
        "stacksmith.runtime.docker_client.DockerClient",
        lambda: SimpleNamespace(get_image_digest=lambda _img: None),
    )
    monkeypatch.setattr(
        "stacksmith.catalog.store.CatalogStore",
        lambda **_kwargs: pytest.fail("CatalogStore should not be constructed when registry policy fails"),
    )
    monkeypatch.setattr(
        "stacksmith.builders.plan_executor.execute_plan",
        lambda *_args, **_kwargs: pytest.fail("execute_plan should not run when registry policy fails"),
    )

    with pytest.raises(RegistryPolicyError):
        ensure_internal("profile1", "stack1")


def test_ensure_internal_continues_when_remote_sync_fails(monkeypatch):
    cfg = AppConfig(
        {
            "registry": {"allow": ["docker.io"], "deny": []},
            "remote_catalog": {
                "enabled": True,
                "repo_url": "https://example.com/catalog.git",
                "branch": "main",
                "local_path": "~/.local/share/stacksmith/remote-catalog",
                "auto_pull": True,
            },
        }
    )
    monkeypatch.setattr("stacksmith.config.AppConfig.load", lambda: cfg)
    monkeypatch.setattr(
        "stacksmith.domain.remote_catalog.sync_remote_catalog",
        lambda _cfg: (_ for _ in ()).throw(RuntimeError("network down")),
    )
    monkeypatch.setattr("stacksmith.config.load_profile", lambda _profile_id: SimpleNamespace(id="p1"))
    monkeypatch.setattr("stacksmith.config.load_stack", lambda _stack_id: SimpleNamespace(id="s1", blocks=[]))
    monkeypatch.setattr(
        "stacksmith.resolvers.resolver.resolve",
        lambda *_args, **_kwargs: SimpleNamespace(
            decision=SimpleNamespace(base_image="docker.io/library/ubuntu:22.04"),
        ),
    )
    monkeypatch.setattr(
        "stacksmith.runtime.docker_client.DockerClient",
        lambda: SimpleNamespace(get_image_digest=lambda _img: None),
    )
    monkeypatch.setattr(
        "stacksmith.catalog.store.CatalogStore",
        lambda **_kwargs: SimpleNamespace(
            upsert_profile=lambda _p: None,
            upsert_stack=lambda _s: None,
        ),
    )
    expected_record = SimpleNamespace(tag="ok:tag")
    monkeypatch.setattr(
        "stacksmith.builders.plan_executor.execute_plan",
        lambda *_args, **_kwargs: expected_record,
    )

    record, _plan = ensure_internal("profile1", "stack1")
    assert record is expected_record

