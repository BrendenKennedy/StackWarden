"""Tests for wizard variant parsing, validation, and normalization."""

from __future__ import annotations

import pytest

from stacksmith.domain.models import StackSpec, VariantDef
from stacksmith.domain.variants import normalize_variants, parse_variants, validate_variant_flags


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_stack(**variant_defs: dict) -> StackSpec:
    variants = {}
    for name, vdef in variant_defs.items():
        variants[name] = VariantDef(**vdef)
    return StackSpec(
        id="test",
        display_name="Test",
        task="llm",
        serve="vllm",
        api="fastapi",
        build_strategy="overlay",
        components={"base_role": "pytorch", "pip": [], "apt": []},
        entrypoint={"cmd": ["python"]},
        variants=variants,
    )


# ---------------------------------------------------------------------------
# parse_variants
# ---------------------------------------------------------------------------


class TestParseVariants:
    def test_empty_input(self):
        assert parse_variants(None) == {}
        assert parse_variants([]) == {}

    def test_basic_string_value(self):
        result = parse_variants(["precision=fp16"])
        assert result == {"precision": "fp16"}

    def test_bool_coercion_true(self):
        result = parse_variants(["xformers=true"])
        assert result["xformers"] is True

    def test_bool_coercion_false(self):
        result = parse_variants(["xformers=false"])
        assert result["xformers"] is False

    def test_bool_case_insensitive(self):
        assert parse_variants(["a=TRUE"])["a"] is True
        assert parse_variants(["a=False"])["a"] is False

    def test_non_bool_stays_string(self):
        result = parse_variants(["mode=bf16"])
        assert result["mode"] == "bf16"
        assert isinstance(result["mode"], str)

    def test_missing_equals_raises(self):
        with pytest.raises(ValueError, match="key=value"):
            parse_variants(["bad_input"])

    def test_multiple_entries(self):
        result = parse_variants(["a=1", "b=true", "c=hello"])
        assert result == {"a": "1", "b": True, "c": "hello"}

    def test_value_with_equals(self):
        result = parse_variants(["key=a=b"])
        assert result == {"key": "a=b"}


# ---------------------------------------------------------------------------
# validate_variant_flags
# ---------------------------------------------------------------------------


class TestValidateVariantFlags:
    def test_valid_key_passes(self):
        stack = _make_stack(precision={"type": "enum", "options": ["fp16", "bf16"], "default": "fp16"})
        validate_variant_flags(stack, {"precision": "bf16"})

    def test_unknown_key_raises(self):
        stack = _make_stack(precision={"type": "enum", "options": ["fp16"], "default": "fp16"})
        with pytest.raises(ValueError, match="Unknown variant 'bogus'"):
            validate_variant_flags(stack, {"bogus": "x"})

    def test_empty_variants_pass(self):
        stack = _make_stack()
        validate_variant_flags(stack, {})


# ---------------------------------------------------------------------------
# normalize_variants
# ---------------------------------------------------------------------------


class TestNormalizeVariants:
    def test_fills_defaults(self):
        stack = _make_stack(
            precision={"type": "enum", "options": ["fp16", "bf16"], "default": "fp16"},
            xformers={"type": "bool", "default": False},
        )
        result = normalize_variants(stack, {})
        assert result == {"precision": "fp16", "xformers": False}

    def test_override_replaces_default(self):
        stack = _make_stack(
            precision={"type": "enum", "options": ["fp16", "bf16"], "default": "fp16"},
        )
        result = normalize_variants(stack, {"precision": "bf16"})
        assert result["precision"] == "bf16"

    def test_bool_string_coerced(self):
        stack = _make_stack(xformers={"type": "bool", "default": False})
        result = normalize_variants(stack, {"xformers": "true"})
        assert result["xformers"] is True

    def test_bool_type_preserved(self):
        stack = _make_stack(xformers={"type": "bool", "default": True})
        result = normalize_variants(stack, {"xformers": False})
        assert result["xformers"] is False
        assert isinstance(result["xformers"], bool)

    def test_enum_rejects_invalid_option(self):
        stack = _make_stack(
            precision={"type": "enum", "options": ["fp16", "bf16"], "default": "fp16"},
        )
        with pytest.raises(ValueError, match="must be one of"):
            normalize_variants(stack, {"precision": "fp64"})

    def test_bool_rejects_non_bool_string(self):
        stack = _make_stack(xformers={"type": "bool", "default": False})
        with pytest.raises(ValueError, match="non-boolean string"):
            normalize_variants(stack, {"xformers": "maybe"})

    def test_unknown_key_rejected(self):
        stack = _make_stack(xformers={"type": "bool", "default": False})
        with pytest.raises(ValueError, match="Unknown variant"):
            normalize_variants(stack, {"bogus": "x"})

    def test_keys_sorted(self):
        stack = _make_stack(
            zeta={"type": "bool", "default": True},
            alpha={"type": "bool", "default": False},
        )
        result = normalize_variants(stack, {})
        assert list(result.keys()) == ["alpha", "zeta"]

    def test_no_variants_returns_empty(self):
        stack = _make_stack()
        result = normalize_variants(stack, {})
        assert result == {}
