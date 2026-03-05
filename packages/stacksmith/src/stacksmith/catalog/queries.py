"""Convenience query functions on top of CatalogStore."""

from __future__ import annotations

from stacksmith.catalog.store import CatalogStore
from stacksmith.domain.enums import ArtifactStatus
from stacksmith.domain.models import ArtifactRecord


def list_artifacts(
    store: CatalogStore,
    profile_id: str | None = None,
    stack_id: str | None = None,
) -> list[ArtifactRecord]:
    return store.search_artifacts(profile_id=profile_id, stack_id=stack_id)


def get_newest_build(
    store: CatalogStore,
    stack_id: str,
    profile_id: str,
) -> ArtifactRecord | None:
    return store.get_newest_build(stack_id, profile_id)


def prune_failed(store: CatalogStore) -> int:
    return store.prune_by_status(ArtifactStatus.FAILED)


def prune_stale(store: CatalogStore) -> int:
    return store.prune_by_status(ArtifactStatus.STALE)
