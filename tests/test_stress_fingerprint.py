"""Stress tests: fingerprint determinism and rebuild idempotence.

- Variant order independence
- Rebuild idempotence (same fingerprint → same tag, no duplicate inserts)
- Template hash affects fingerprint
"""

from __future__ import annotations

import pytest

from stackwarden.domain.hashing import canonicalize, fingerprint, generate_tag
from stackwarden.domain.models import (
    BaseCandidate,
    CudaSpec,
    GpuSpec,
    PipDep,
    Profile,
    StackComponents,
    StackEntrypoint,
    StackSpec,
)


def _profile(**kw) -> Profile:
    defaults = dict(
        id="stress_p",
        display_name="Stress",
        arch="arm64",
        cuda=CudaSpec(major=12, minor=5, variant="cuda12.5"),
        gpu=GpuSpec(vendor="nvidia", family="test"),
        base_candidates=[BaseCandidate(name="pytorch", tags=["latest"])],
    )
    defaults.update(kw)
    return Profile.model_validate(defaults)


def _stack(**kw) -> StackSpec:
    defaults = dict(
        id="stress_s",
        display_name="Stress",
        task="diffusion",
        serve="python_api",
        api="fastapi",
        build_strategy="overlay",
        components=StackComponents(
            base_role="pytorch",
            pip=[PipDep(name="a", version="1"), PipDep(name="b", version="2")],
        ),
        entrypoint=StackEntrypoint(cmd=["python", "main.py"]),
    )
    defaults.update(kw)
    return StackSpec.model_validate(defaults)


class TestVariantOrderIndependence:
    """Variant order in canonical form must not affect fingerprint."""

    def test_pip_order_independent(self):
        p = _profile()
        s1 = _stack(components=StackComponents(
            base_role="pytorch",
            pip=[PipDep(name="z", version="1"), PipDep(name="a", version="2")],
        ))
        s2 = _stack(components=StackComponents(
            base_role="pytorch",
            pip=[PipDep(name="a", version="2"), PipDep(name="z", version="1")],
        ))
        assert canonicalize(p, s1, "base") == canonicalize(p, s2, "base")
        assert fingerprint(p, s1, "base:latest") == fingerprint(p, s2, "base:latest")

    def test_env_order_independent(self):
        p = _profile()
        s1 = _stack(env=["Z=1", "A=2"])
        s2 = _stack(env=["A=2", "Z=1"])
        assert fingerprint(p, s1, "base:latest") == fingerprint(p, s2, "base:latest")

    def test_apt_order_independent(self):
        p = _profile()
        s1 = _stack(components=StackComponents(base_role="pytorch", apt=["curl", "git"]))
        s2 = _stack(components=StackComponents(base_role="pytorch", apt=["git", "curl"]))
        assert fingerprint(p, s1, "base:latest") == fingerprint(p, s2, "base:latest")


class TestTemplateHashAffectsFingerprint:
    """Template hash must be included in fingerprint."""

    def test_different_template_hash_different_fp(self):
        p, s = _profile(), _stack()
        fp1 = fingerprint(p, s, "base:latest", template_hash="v1")
        fp2 = fingerprint(p, s, "base:latest", template_hash="v2")
        assert fp1 != fp2

    def test_same_template_hash_same_fp(self):
        p, s = _profile(), _stack()
        fp1 = fingerprint(p, s, "base:latest", template_hash="v1")
        fp2 = fingerprint(p, s, "base:latest", template_hash="v1")
        assert fp1 == fp2


class TestRebuildIdempotence:
    """Rebuild with same fingerprint: same tag, no unique constraint violation."""

    def test_same_inputs_same_tag(self):
        p, s = _profile(), _stack()
        fp = fingerprint(p, s, "base:latest")
        tag1 = generate_tag(s, p, fp)
        tag2 = generate_tag(s, p, fp)
        assert tag1 == tag2

    def test_rebuild_prunes_old_before_insert(self, tmp_path):
        """Plan executor prunes by fingerprint before insert to avoid unique constraint."""
        from unittest.mock import MagicMock, patch

        from stackwarden.builders.plan_executor import _do_execute
        from stackwarden.catalog.store import CatalogStore
        from stackwarden.domain.enums import ArtifactStatus
        from stackwarden.domain.models import Plan, PlanArtifact, PlanDecision

        plan = Plan(
            plan_id="x",
            profile_id="p1",
            stack_id="s1",
            decision=PlanDecision(base_image="base:latest", base_digest="sha256:aaa", builder="overlay"),
            steps=[],
            artifact=PlanArtifact(
                tag="local/stackwarden:test",
                fingerprint="fp123",
                labels={"stackwarden.variants": "{}", "stackwarden.schema_version": "1"},
            ),
        )
        profile = _profile(id="p1")
        stack = _stack(id="s1")
        catalog = CatalogStore(db_path=tmp_path / "stress.db")
        # Ensure profile/stack rows exist
        from stackwarden.catalog.models import ProfileRow, StackRow
        with catalog._session() as s:
            if not s.get(ProfileRow, "p1"):
                s.add(ProfileRow(id="p1", display_name="P1", arch="amd64", cuda_variant="none", data_json="{}"))
            if not s.get(StackRow, "s1"):
                s.add(StackRow(id="s1", display_name="S1", task="llm", serve="vllm", api="fastapi", data_json="{}"))
            s.commit()

        docker = MagicMock()
        docker.image_exists.return_value = False
        docker.get_image_id.return_value = "abc123"
        docker.get_image_digest.return_value = "sha256:xyz"

        builder = MagicMock()
        builder.can_build.return_value = True
        builder.execute.return_value = MagicMock(tag=plan.artifact.tag, image_id="x", digest="y")
        mock_registry = {"overlay": builder}

        with patch("stackwarden.builders.plan_executor.BUILDER_REGISTRY", mock_registry), \
             patch("stackwarden.builders.plan_executor._run_hooks"):
            # First build
            rec1 = _do_execute(plan, profile, stack, docker, catalog, rebuild=True)
            assert rec1.status == ArtifactStatus.BUILT

            # Rebuild (same fingerprint) — should prune old then insert, no unique violation
            rec2 = _do_execute(plan, profile, stack, docker, catalog, rebuild=True)
            assert rec2.status == ArtifactStatus.BUILT
            assert rec2.fingerprint == plan.artifact.fingerprint
