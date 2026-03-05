"""Variant hashing determinism and type validation tests."""

from __future__ import annotations

import pytest

from stackwarden.domain.models import VariantDef, StackSpec
from stackwarden.domain.hashing import canonicalize, fingerprint


class TestVariantDefValidation:
    def test_enum_requires_options(self):
        with pytest.raises(ValueError, match="enum variant must declare options"):
            VariantDef(type="enum", default="x")

    def test_enum_with_options_ok(self):
        v = VariantDef(type="enum", options=["a", "b"], default="a")
        assert v.type == "enum"
        assert v.options == ["a", "b"]

    def test_bool_requires_bool_default(self):
        with pytest.raises(ValueError, match="bool variant must have a bool default"):
            VariantDef(type="bool", default="yes")

    def test_bool_ok(self):
        v = VariantDef(type="bool", default=False)
        assert v.type == "bool"
        assert v.default is False


class TestVariantHashing:
    @pytest.fixture
    def dummy_profile(self):
        from stackwarden.domain.models import Profile, CudaSpec, GpuSpec, BaseCandidate
        return Profile(
            id="test",
            display_name="Test",
            arch="amd64",
            cuda=CudaSpec(major=12, minor=0, variant="cuda12.0"),
            gpu=GpuSpec(vendor="nvidia", family="ampere"),
            base_candidates=[BaseCandidate(name="base", tags=["latest"])],
        )

    @pytest.fixture
    def dummy_stack(self):
        return StackSpec(
            id="test_stack",
            display_name="Test Stack",
            task="llm",
            serve="vllm",
            api="fastapi",
            build_strategy="overlay",
            components={"base_role": "pytorch", "pip": [], "apt": []},
            entrypoint={"cmd": ["python"]},
        )

    def test_variant_changes_fingerprint(self, dummy_profile, dummy_stack):
        fp1 = fingerprint(
            dummy_profile, dummy_stack, "base:latest",
            variants={"precision": "fp16"},
        )
        fp2 = fingerprint(
            dummy_profile, dummy_stack, "base:latest",
            variants={"precision": "bf16"},
        )
        assert fp1 != fp2

    def test_variant_order_irrelevant(self, dummy_profile, dummy_stack):
        fp1 = fingerprint(
            dummy_profile, dummy_stack, "base:latest",
            variants={"a": "1", "b": "2"},
        )
        fp2 = fingerprint(
            dummy_profile, dummy_stack, "base:latest",
            variants={"b": "2", "a": "1"},
        )
        assert fp1 == fp2

    def test_no_variants_deterministic(self, dummy_profile, dummy_stack):
        fp1 = fingerprint(dummy_profile, dummy_stack, "base:latest")
        fp2 = fingerprint(dummy_profile, dummy_stack, "base:latest")
        assert fp1 == fp2
