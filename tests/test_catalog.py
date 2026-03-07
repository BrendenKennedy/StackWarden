"""Tests for catalog CRUD with in-memory SQLite."""


import pytest
from sqlalchemy import text

from stackwarden.catalog.store import CatalogStore
from stackwarden.domain.enums import ArtifactStatus, LicenseSeverity
from stackwarden.domain.models import (
    ArtifactComponent,
    ArtifactRecord,
    BaseCandidate,
    CudaSpec,
    GpuSpec,
    Profile,
    StackComponents,
    StackEntrypoint,
    StackSpec,
)


@pytest.fixture
def store(tmp_path):
    return CatalogStore(tmp_path / "test.db")


@pytest.fixture
def profile():
    return Profile.model_validate(dict(
        id="test_profile",
        display_name="Test",
        arch="arm64",
        cuda=CudaSpec(major=12, minor=5, variant="cuda12.5"),
        gpu=GpuSpec(vendor="nvidia", family="test"),
        base_candidates=[BaseCandidate(name="pytorch", tags=["latest"])],
    ))


@pytest.fixture
def stack():
    return StackSpec.model_validate(dict(
        id="test_stack",
        display_name="Test",
        task="diffusion",
        serve="python_api",
        api="fastapi",
        build_strategy="overlay",
        components=StackComponents(base_role="pytorch"),
        entrypoint=StackEntrypoint(cmd=["python", "main.py"]),
    ))


_fp_counter = 0


def _artifact(tag="local/stackwarden:test", status=ArtifactStatus.BUILDING, **kw):
    global _fp_counter
    _fp_counter += 1
    defaults = dict(
        id=kw.pop("id", "art1"),
        profile_id="test_profile",
        stack_id="test_stack",
        tag=tag,
        fingerprint=kw.pop("fingerprint", f"fp_{_fp_counter:06d}"),
        base_image="pytorch:latest",
        build_strategy="overlay",
        status=status,
    )
    defaults.update(kw)
    return ArtifactRecord(**defaults)


class TestProfileStacks:
    def test_upsert_profile(self, store, profile):
        store.upsert_profile(profile)
        profiles = store.list_profiles()
        assert len(profiles) == 1
        assert profiles[0]["id"] == "test_profile"

    def test_upsert_profile_update(self, store, profile):
        store.upsert_profile(profile)
        profile.display_name = "Updated"
        store.upsert_profile(profile)
        profiles = store.list_profiles()
        assert len(profiles) == 1

    def test_upsert_stack(self, store, stack):
        store.upsert_stack(stack)
        stacks = store.list_stacks()
        assert len(stacks) == 1
        assert stacks[0]["id"] == "test_stack"


class TestArtifacts:
    def test_insert_and_retrieve(self, store, profile, stack):
        store.upsert_profile(profile)
        store.upsert_stack(stack)
        art = _artifact()
        store.insert_artifact(art)
        found = store.get_artifact_by_tag("local/stackwarden:test")
        assert found is not None
        assert found.id == "art1"
        assert found.status == ArtifactStatus.BUILDING

    def test_update_status(self, store, profile, stack):
        store.upsert_profile(profile)
        store.upsert_stack(stack)
        art = _artifact()
        store.insert_artifact(art)
        store.update_artifact_status("art1", ArtifactStatus.BUILT)
        found = store.get_artifact_by_tag("local/stackwarden:test")
        assert found.status == ArtifactStatus.BUILT

    def test_mark_stale(self, store, profile, stack):
        store.upsert_profile(profile)
        store.upsert_stack(stack)
        store.insert_artifact(_artifact(id="a1", tag="t1", status=ArtifactStatus.BUILT))
        store.insert_artifact(_artifact(id="a2", tag="t2", status=ArtifactStatus.BUILT))
        count = store.mark_stale("test_profile", "test_stack")
        assert count == 2
        for tag in ["t1", "t2"]:
            assert store.get_artifact_by_tag(tag).status == ArtifactStatus.STALE

    def test_search_by_profile(self, store, profile, stack):
        store.upsert_profile(profile)
        store.upsert_stack(stack)
        store.insert_artifact(_artifact(id="a1", tag="t1"))
        results = store.search_artifacts(profile_id="test_profile")
        assert len(results) == 1

    def test_search_by_status(self, store, profile, stack):
        store.upsert_profile(profile)
        store.upsert_stack(stack)
        store.insert_artifact(_artifact(id="a1", tag="t1", status=ArtifactStatus.BUILT))
        store.insert_artifact(_artifact(id="a2", tag="t2", status=ArtifactStatus.FAILED))
        results = store.search_artifacts(status="built")
        assert len(results) == 1
        assert results[0].status == ArtifactStatus.BUILT

    def test_get_newest_build(self, store, profile, stack):
        store.upsert_profile(profile)
        store.upsert_stack(stack)
        store.insert_artifact(_artifact(id="a1", tag="t1", status=ArtifactStatus.BUILT))
        newest = store.get_newest_build("test_stack", "test_profile")
        assert newest is not None
        assert newest.id == "a1"

    def test_prune_failed(self, store, profile, stack):
        store.upsert_profile(profile)
        store.upsert_stack(stack)
        store.insert_artifact(_artifact(id="a1", tag="t1", status=ArtifactStatus.FAILED))
        store.insert_artifact(_artifact(id="a2", tag="t2", status=ArtifactStatus.BUILT))
        count = store.prune_by_status(ArtifactStatus.FAILED)
        assert count == 1
        assert store.get_artifact_by_tag("t1") is None
        assert store.get_artifact_by_tag("t2") is not None

    def test_prune_stale(self, store, profile, stack):
        store.upsert_profile(profile)
        store.upsert_stack(stack)
        store.insert_artifact(_artifact(id="a1", tag="t1", status=ArtifactStatus.STALE))
        count = store.prune_by_status(ArtifactStatus.STALE)
        assert count == 1

    def test_prefers_legacy_block_schema_when_layer_schema_is_default(self, store, profile, stack):
        store.upsert_profile(profile)
        store.upsert_stack(stack)
        store.insert_artifact(_artifact(id="a1", tag="t1", layer_schema_version=1))
        with store._engine.begin() as conn:  # noqa: SLF001
            conn.execute(text(
                "UPDATE artifacts SET block_schema_version = 3, layer_schema_version = 1 WHERE id = 'a1'"
            ))
        found = store.get_artifact_by_tag("t1")
        assert found is not None
        assert found.layer_schema_version == 3


class TestComponents:
    def test_insert_and_retrieve_components(self, store, profile, stack):
        store.upsert_profile(profile)
        store.upsert_stack(stack)
        store.insert_artifact(_artifact(id="a1", tag="t1"))
        components = [
            ArtifactComponent(
                artifact_id="a1", type="pip", name="fastapi",
                version="0.115.0", license_spdx="MIT",
                license_severity=LicenseSeverity.OK,
            ),
            ArtifactComponent(
                artifact_id="a1", type="apt", name="git",
            ),
        ]
        store.insert_components(components)
        result = store.get_components("a1")
        assert len(result) == 2
        pip_comp = next(c for c in result if c["type"] == "pip")
        assert pip_comp["license_spdx"] == "MIT"
        assert pip_comp["license_severity"] == "ok"
