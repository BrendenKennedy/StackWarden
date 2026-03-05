"""Prune safety tests — newest stable protection."""

from __future__ import annotations

import pytest

from stacksmith.catalog.store import CatalogStore
from stacksmith.domain.enums import ArtifactStatus
from stacksmith.domain.models import ArtifactRecord


@pytest.fixture
def catalog(tmp_path):
    return CatalogStore(db_path=tmp_path / "test.db")


def _artifact(catalog, profile_id="p1", stack_id="s1", tag="t1", fp="fp1",
              status=ArtifactStatus.BUILT, **kw) -> ArtifactRecord:
    import uuid
    r = ArtifactRecord(
        id=uuid.uuid4().hex[:16],
        profile_id=profile_id,
        stack_id=stack_id,
        tag=tag,
        fingerprint=fp,
        base_image="base:latest",
        build_strategy="overlay",
        status=status,
        **kw,
    )
    from stacksmith.catalog.models import ProfileRow, StackRow

    with catalog._session() as s:
        if not s.get(ProfileRow, profile_id):
            s.add(ProfileRow(
                id=profile_id, display_name=profile_id, arch="amd64",
                cuda_variant="cuda12", data_json="{}",
            ))
        if not s.get(StackRow, stack_id):
            s.add(StackRow(
                id=stack_id, display_name=stack_id, task="llm",
                serve="vllm", api="fastapi", data_json="{}",
            ))
        s.commit()

    catalog.insert_artifact(r)
    return r


class TestPruneSafety:
    def test_prune_stale(self, catalog):
        _artifact(catalog, tag="t1", fp="fp1", status=ArtifactStatus.STALE)
        count = catalog.prune_by_status(ArtifactStatus.STALE)
        assert count == 1

    def test_prune_failed(self, catalog):
        _artifact(catalog, tag="t1", fp="fp1", status=ArtifactStatus.FAILED)
        count = catalog.prune_by_status(ArtifactStatus.FAILED)
        assert count == 1

    def test_find_unused_protects_newest(self, catalog):
        r1 = _artifact(catalog, tag="t1", fp="fp1")
        r2 = _artifact(catalog, tag="t2", fp="fp2")

        unused = catalog.find_unused(force=False)
        unused_ids = {u.id for u in unused}
        assert r1.id in unused_ids  # older
        assert r2.id not in unused_ids  # newest — protected

    def test_find_unused_force_includes_newest(self, catalog):
        _artifact(catalog, tag="t1", fp="fp1")
        r2 = _artifact(catalog, tag="t2", fp="fp2")

        unused = catalog.find_unused(force=True)
        unused_ids = {u.id for u in unused}
        assert r2.id in unused_ids

    def test_count_protected(self, catalog):
        _artifact(catalog, tag="t1", fp="fp1")
        _artifact(catalog, tag="t2", fp="fp2")
        assert catalog.count_protected() == 1  # one group, one protected
