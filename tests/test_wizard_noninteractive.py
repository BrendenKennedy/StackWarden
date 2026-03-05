"""Tests for wizard non-interactive mode and JSON output schema."""

from __future__ import annotations

import json

import pytest

from stackwarden.domain.models import (
    BaseCandidate,
    CudaSpec,
    GpuSpec,
    Profile,
    StackSpec,
    VariantDef,
)
from stackwarden.ui.wizard import (
    WizardFlags,
    WizardResult,
    WizardSelection,
    build_command,
    render_plan_json,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _disable_tuple_layer(monkeypatch):
    monkeypatch.setenv("STACKWARDEN_TUPLE_LAYER_MODE", "off")


def _make_profile(pid: str = "test_profile") -> Profile:
    return Profile(
        id=pid,
        display_name="Test Profile",
        arch="amd64",
        cuda=CudaSpec(major=12, minor=0, variant="cuda12.0"),
        gpu=GpuSpec(vendor="nvidia", family="ampere"),
        capabilities=["cuda", "tensor_cores"],
        base_candidates=[BaseCandidate(name="nvcr.io/nvidia/pytorch", tags=["24.06-py3"])],
    )


def _make_stack(
    sid: str = "test_stack",
    variants: dict | None = None,
) -> StackSpec:
    return StackSpec(
        id=sid,
        display_name="Test Stack",
        task="llm",
        serve="vllm",
        api="fastapi",
        build_strategy="overlay",
        components={"base_role": "pytorch", "pip": [], "apt": []},
        entrypoint={"cmd": ["python"]},
        variants=variants or {},
    )


# ---------------------------------------------------------------------------
# WizardResult schema
# ---------------------------------------------------------------------------


class TestWizardResultSchema:
    def test_json_roundtrip(self):
        result = WizardResult(
            selection=WizardSelection(
                profile_id="x86_cuda",
                stack_id="llm_vllm",
                variants={"precision": "fp16", "xformers": True},
                flags=WizardFlags(immutable=True),
            ),
            plan_summary={"base_image": "nvcr.io/nvidia/pytorch:24.06-py3"},
            warnings=["mutable base tag"],
            digest_status="unknown_until_pull",
            command="stackwarden ensure --profile x86_cuda --stack llm_vllm",
            executed=False,
            tag=None,
        )
        data = json.loads(result.model_dump_json())
        assert data["selection"]["profile_id"] == "x86_cuda"
        assert data["selection"]["stack_id"] == "llm_vllm"
        assert data["selection"]["variants"]["precision"] == "fp16"
        assert data["selection"]["variants"]["xformers"] is True
        assert data["selection"]["flags"]["immutable"] is True
        assert data["warnings"] == ["mutable base tag"]
        assert data["digest_status"] == "unknown_until_pull"
        assert data["command"].startswith("stackwarden ensure")
        assert data["executed"] is False
        assert data["tag"] is None

    def test_executed_result_has_tag(self):
        result = WizardResult(
            selection=WizardSelection(profile_id="p", stack_id="s"),
            command="stackwarden ensure --profile p --stack s",
            executed=True,
            tag="stackwarden:p_s_abc123",
        )
        data = json.loads(result.model_dump_json())
        assert data["executed"] is True
        assert data["tag"] == "stackwarden:p_s_abc123"

    def test_all_fields_present(self):
        result = WizardResult(
            selection=WizardSelection(profile_id="p", stack_id="s"),
            command="cmd",
        )
        data = json.loads(result.model_dump_json())
        expected_keys = {
            "selection", "plan_summary", "warnings", "digest_status",
            "command", "executed", "tag",
        }
        assert set(data.keys()) == expected_keys


# ---------------------------------------------------------------------------
# render_plan_json
# ---------------------------------------------------------------------------


class TestRenderPlanJson:
    def test_contains_expected_keys(self):
        from stackwarden.resolvers.resolver import resolve

        profile = _make_profile()
        stack = _make_stack()
        plan = resolve(profile, stack)
        selection = WizardSelection(profile_id="test_profile", stack_id="test_stack")
        data = render_plan_json(plan, selection)

        for key in [
            "plan_id", "profile_id", "stack_id", "base_image",
            "base_digest", "digest_status", "output_tag", "fingerprint",
            "strategy", "warnings", "steps", "variants",
        ]:
            assert key in data, f"Missing key: {key}"

    def test_digest_status_unknown_when_no_digest(self):
        from stackwarden.resolvers.resolver import resolve

        profile = _make_profile()
        stack = _make_stack()
        plan = resolve(profile, stack)
        selection = WizardSelection(profile_id="test_profile", stack_id="test_stack")
        data = render_plan_json(plan, selection)
        assert data["digest_status"] == "unknown_until_pull"

    def test_digest_status_known_when_digest_present(self):
        from stackwarden.resolvers.resolver import resolve

        profile = _make_profile()
        stack = _make_stack()
        plan = resolve(profile, stack, base_digest="sha256:abc123")
        selection = WizardSelection(profile_id="test_profile", stack_id="test_stack")
        data = render_plan_json(plan, selection)
        assert data["digest_status"] == "known"

    def test_variants_in_output(self):
        from stackwarden.resolvers.resolver import resolve

        profile = _make_profile()
        stack = _make_stack()
        plan = resolve(profile, stack, variants={"precision": "fp16"})
        selection = WizardSelection(
            profile_id="test_profile",
            stack_id="test_stack",
            variants={"precision": "fp16"},
        )
        data = render_plan_json(plan, selection)
        assert data["variants"] == {"precision": "fp16"}


# ---------------------------------------------------------------------------
# Defaults mode
# ---------------------------------------------------------------------------


class TestDefaultsMode:
    def test_defaults_flag_creates_valid_selection(self):
        sel = WizardSelection(
            profile_id="x86_cuda",
            stack_id="llm_vllm",
            variants={"precision": "fp16"},
            flags=WizardFlags(),
        )
        cmd = build_command(sel)
        assert "--profile x86_cuda" in cmd
        assert "--stack llm_vllm" in cmd
        assert "--var precision=fp16" in cmd
