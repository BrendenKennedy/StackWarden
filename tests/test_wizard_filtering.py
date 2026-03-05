"""Tests for wizard compatible stack selection."""

from __future__ import annotations

from stacksmith.domain.models import (
    BaseCandidate,
    CudaSpec,
    GpuSpec,
    Profile,
    StackSpec,
)
from stacksmith.ui.wizard import (
    filter_compatible_stacks,
    choose_stack,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_profile(
    pid: str = "test",
    arch: str = "amd64",
    capabilities: list[str] | None = None,
) -> Profile:
    return Profile(
        id=pid,
        display_name="Test",
        arch=arch,
        cuda=CudaSpec(major=12, minor=0, variant="cuda12.0"),
        gpu=GpuSpec(vendor="nvidia", family="ampere"),
        capabilities=capabilities or ["cuda", "tensor_cores"],
        base_candidates=[BaseCandidate(name="base", tags=["latest"])],
    )


def _make_stack(
    sid: str,
    task: str = "llm",
    serve: str = "vllm",
    api: str = "fastapi",
) -> StackSpec:
    return StackSpec(
        id=sid,
        display_name=f"Stack {sid}",
        task=task,
        serve=serve,
        api=api,
        build_strategy="overlay",
        components={"base_role": "pytorch", "pip": [], "apt": []},
        entrypoint={"cmd": ["python"]},
    )


# ---------------------------------------------------------------------------
# filter_compatible_stacks
# ---------------------------------------------------------------------------


class TestFilterCompatibleStacks:
    def test_keeps_compatible(self):
        profile = _make_profile()
        s1 = _make_stack("ok", serve="python_api")
        result = filter_compatible_stacks([s1], profile)
        assert len(result) == 1
        assert result[0].id == "ok"

    def test_removes_incompatible_serve(self):
        profile = _make_profile()
        profile.constraints.disallow["serve"] = ["vllm"]
        s1 = _make_stack("bad", serve="vllm")
        result = filter_compatible_stacks([s1], profile)
        assert result == []

    def test_mixed(self):
        profile = _make_profile()
        profile.constraints.disallow["serve"] = ["triton"]
        s_ok = _make_stack("ok", serve="python_api")
        s_bad = _make_stack("bad", serve="triton")
        result = filter_compatible_stacks([s_ok, s_bad], profile)
        assert [s.id for s in result] == ["ok"]


class TestChooseStack:
    def test_returns_single_match_without_prompt(self):
        s1 = _make_stack("s1")
        assert choose_stack([s1]) == "s1"
