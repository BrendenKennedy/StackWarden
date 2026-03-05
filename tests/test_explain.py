"""Tests for resolver explainability (--explain)."""

from __future__ import annotations

import pytest

from stacksmith.domain.models import (
    BaseCandidate,
    CudaSpec,
    DecisionRationale,
    GpuSpec,
    PipDep,
    Profile,
    ScoreBreakdown,
    StackComponents,
    StackEntrypoint,
    StackSpec,
)
from stacksmith.resolvers.resolver import resolve
from stacksmith.resolvers.scoring import score_candidate_detailed, select_base_detailed


def _profile(**kw) -> Profile:
    defaults = dict(
        id="test_profile",
        display_name="Test",
        arch="arm64",
        cuda=CudaSpec(major=12, minor=5, variant="cuda12.5"),
        gpu=GpuSpec(vendor="nvidia", family="test"),
        capabilities=["cuda"],
        base_candidates=[
            BaseCandidate(name="nvcr.io/nvidia/pytorch", tags=["24.06-py3"], score_bias=0),
            BaseCandidate(name="nvcr.io/nvidia/tritonserver", tags=["24.06-py3"], score_bias=0),
        ],
    )
    defaults.update(kw)
    return Profile.model_validate(defaults)


def _stack(**kw) -> StackSpec:
    defaults = dict(
        id="test_stack",
        display_name="Test",
        task="diffusion",
        serve="python_api",
        api="fastapi",
        build_strategy="overlay",
        components=StackComponents(
            base_role="pytorch",
            pip=[PipDep(name="torch", version=">=2.0")],
        ),
        entrypoint=StackEntrypoint(cmd=["python"]),
    )
    defaults.update(kw)
    return StackSpec.model_validate(defaults)


class TestScoreBreakdown:
    def test_score_breakdown_fields(self):
        p = _profile()
        s = _stack()
        bd = score_candidate_detailed(p.base_candidates[0], s, p)
        assert isinstance(bd, ScoreBreakdown)
        assert bd.candidate_name == "nvcr.io/nvidia/pytorch"
        assert bd.role_match == 200  # "pytorch" in name
        assert bd.total == bd.score_bias + bd.role_match + bd.cuda_match

    def test_no_role_match(self):
        p = _profile()
        s = _stack()
        bd = score_candidate_detailed(p.base_candidates[1], s, p)
        assert bd.role_match == 0  # "pytorch" not in "tritonserver"

    def test_cuda_match_detected(self):
        p = _profile()
        p.base_candidates[0].tags = ["cuda12.5-py3"]
        s = _stack()
        bd = score_candidate_detailed(p.base_candidates[0], s, p)
        assert bd.cuda_match == 50


class TestSelectBaseDetailed:
    def test_returns_breakdowns(self):
        p = _profile()
        s = _stack()
        candidate, tag, breakdowns, reason = select_base_detailed(p, s)
        assert len(breakdowns) == 2
        assert all(isinstance(b, ScoreBreakdown) for b in breakdowns)
        assert candidate.name == "nvcr.io/nvidia/pytorch"
        assert "pytorch" in reason.lower() or "role" in reason.lower()

    def test_reason_explains_selection(self):
        p = _profile()
        s = _stack()
        _, _, _, reason = select_base_detailed(p, s)
        assert "role match" in reason.lower()


class TestResolveExplain:
    def test_explain_false_no_rationale(self):
        p = _profile()
        s = _stack()
        plan = resolve(p, s, explain=False)
        assert plan.decision.rationale is None

    def test_explain_true_has_rationale(self):
        p = _profile()
        s = _stack()
        plan = resolve(p, s, explain=True)
        assert plan.decision.rationale is not None
        rat = plan.decision.rationale
        assert isinstance(rat, DecisionRationale)

    def test_rationale_has_candidates(self):
        p = _profile()
        s = _stack()
        plan = resolve(p, s, explain=True)
        rat = plan.decision.rationale
        assert len(rat.candidates) == 2

    def test_rationale_rules_fired(self):
        p = _profile()
        s = _stack()
        plan = resolve(p, s, explain=True)
        rat = plan.decision.rationale
        assert len(rat.rules_fired) > 0
        for rule in rat.rules_fired:
            assert "rule" in rule
            assert "outcome" in rule

    def test_base_digest_status_unknown(self):
        p = _profile()
        s = _stack()
        plan = resolve(p, s, explain=True)
        assert plan.decision.rationale.base_digest_status == "unknown_until_pull"

    def test_base_digest_status_known(self):
        p = _profile()
        s = _stack()
        plan = resolve(p, s, base_digest="sha256:abc", explain=True)
        assert plan.decision.rationale.base_digest_status == "known"

    def test_variant_effects(self):
        p = _profile()
        s = _stack(variants={"precision": {"type": "enum", "options": ["fp16", "bf16"], "default": "fp16"}})
        plan = resolve(p, s, variants={"precision": "bf16"}, explain=True)
        assert any("VARIANT_PRECISION" in e for e in plan.decision.rationale.variant_effects)
