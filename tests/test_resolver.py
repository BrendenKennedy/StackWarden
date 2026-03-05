"""Tests for resolver rules, scoring, and plan generation."""

import pytest

from stackwarden.domain.errors import IncompatibleStackError
from stackwarden.domain.models import (
    BaseCandidate,
    CudaSpec,
    GpuSpec,
    PipDep,
    Profile,
    ProfileConstraints,
    StackComponents,
    StackEntrypoint,
    StackSpec,
)
from stackwarden.resolvers.resolver import resolve
from stackwarden.resolvers.rules import (
    check_arch_compatibility,
    check_required_capabilities,
    check_serve_disallowed,
    evaluate_all,
)
from stackwarden.resolvers.scoring import score_candidate, select_base
from stackwarden.resolvers.validators import validate_profile, validate_stack


@pytest.fixture(autouse=True)
def _tuple_layer_off(monkeypatch):
    monkeypatch.setenv("STACKWARDEN_TUPLE_LAYER_MODE", "off")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _profile(**kw) -> Profile:
    defaults = dict(
        id="test",
        display_name="Test",
        arch="arm64",
        cuda=CudaSpec(major=12, minor=5, variant="cuda12.5"),
        gpu=GpuSpec(vendor="nvidia", family="test"),
        derived_capabilities=["cuda", "tensor_cores"],
        base_candidates=[
            BaseCandidate(name="nvcr.io/nvidia/pytorch", tags=["24.06-py3"], score_bias=100),
            BaseCandidate(name="nvcr.io/nvidia/tritonserver", tags=["24.06-py3"], score_bias=70),
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
        components=StackComponents(base_role="pytorch"),
        entrypoint=StackEntrypoint(cmd=["python", "main.py"]),
    )
    defaults.update(kw)
    return StackSpec.model_validate(defaults)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


class TestRules:
    def test_arch_warns_on_xformers(self):
        p = _profile(arch="arm64")
        s = _stack(components=StackComponents(
            base_role="pytorch",
            pip=[PipDep(name="xformers", version=">=0.0.20")],
        ))
        issues = check_arch_compatibility(p, s)
        assert len(issues) == 1
        assert "xformers" in issues[0]

    def test_arch_no_warning_on_amd64(self):
        p = _profile(arch="amd64")
        s = _stack(components=StackComponents(
            base_role="pytorch",
            pip=[PipDep(name="xformers", version=">=0.0.20")],
        ))
        assert check_arch_compatibility(p, s) == []

    def test_disallowed_serve(self):
        p = _profile(constraints=ProfileConstraints(disallow={"serve": ["vllm"]}))
        s = _stack(serve="vllm")
        issues = check_serve_disallowed(p, s)
        assert len(issues) == 1
        assert "ERROR:" in issues[0]

    def test_allowed_serve_passes(self):
        p = _profile()
        s = _stack(serve="python_api")
        assert check_serve_disallowed(p, s) == []

    def test_missing_capability_errors(self):
        p = _profile(cuda=None, container_runtime="runc", derived_capabilities=[])
        s = _stack(serve="vllm")
        issues = check_required_capabilities(p, s)
        assert any("cuda" in i for i in issues)

    def test_evaluate_all_splits(self):
        p = _profile(arch="arm64")
        s = _stack(components=StackComponents(
            base_role="pytorch",
            pip=[PipDep(name="xformers")],
        ))
        warnings, errors = evaluate_all(p, s)
        assert len(warnings) == 1
        assert errors == []


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class TestScoring:
    def test_role_match_scores_higher(self):
        p = _profile()
        s = _stack(components=StackComponents(base_role="pytorch"))
        pytorch = p.base_candidates[0]
        triton = p.base_candidates[1]
        assert score_candidate(pytorch, s, p) > score_candidate(triton, s, p)

    def test_select_base_deterministic(self):
        p = _profile()
        s = _stack()
        c1, t1 = select_base(p, s)
        c2, t2 = select_base(p, s)
        assert c1.name == c2.name
        assert t1 == t2

    def test_select_base_picks_pytorch(self):
        p = _profile()
        s = _stack(components=StackComponents(base_role="pytorch"))
        candidate, tag = select_base(p, s)
        assert "pytorch" in candidate.name


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


class TestValidators:
    def test_empty_base_candidates_rejected(self):
        from stackwarden.domain.errors import ValidationError
        p = _profile(base_candidates=[])
        with pytest.raises(ValidationError):
            validate_profile(p)

    def test_valid_profile_passes(self):
        validate_profile(_profile())

    def test_empty_base_role_rejected(self):
        from stackwarden.domain.errors import ValidationError
        s = _stack(components=StackComponents(base_role=""))
        with pytest.raises(ValidationError):
            validate_stack(s)


# ---------------------------------------------------------------------------
# Resolver (pure function verification)
# ---------------------------------------------------------------------------


class TestResolver:
    def test_resolve_returns_plan(self):
        p = _profile()
        s = _stack()
        plan = resolve(p, s)
        assert plan.profile_id == "test"
        assert plan.stack_id == "test_stack"
        assert plan.artifact.tag.startswith("local/stackwarden:")
        assert len(plan.steps) >= 1

    def test_resolve_deterministic(self):
        p = _profile()
        s = _stack()
        plan1 = resolve(p, s)
        plan2 = resolve(p, s)
        assert plan1.artifact.fingerprint == plan2.artifact.fingerprint
        assert plan1.artifact.tag == plan2.artifact.tag

    def test_resolve_includes_labels(self):
        p = _profile()
        s = _stack()
        plan = resolve(p, s)
        labels = plan.artifact.labels
        assert "stackwarden.profile" in labels
        assert "stackwarden.stack" in labels
        assert "stackwarden.fingerprint" in labels
        assert labels["stackwarden.profile"] == "test"

    def test_resolve_incompatible_raises(self):
        p = _profile(cuda=None, container_runtime="runc", derived_capabilities=[])
        s = _stack(serve="vllm")
        with pytest.raises(IncompatibleStackError):
            resolve(p, s)

    def test_resolve_is_pure_no_side_effects(self):
        """Resolver must not import or call Docker, filesystem, or catalog modules."""
        import sys
        p = _profile()
        s = _stack()

        docker_loaded_before = "docker" in sys.modules
        resolve(p, s)

        if not docker_loaded_before:
            assert "docker" not in sys.modules, "Resolver must not import docker"

    def test_resolve_overlay_has_build_step(self):
        p = _profile()
        s = _stack(build_strategy="overlay")
        plan = resolve(p, s)
        step_types = [step.type for step in plan.steps]
        assert "build_overlay" in step_types

    def test_resolve_pull_has_tag_step(self):
        p = _profile()
        s = _stack(build_strategy="pull")
        plan = resolve(p, s)
        step_types = [step.type for step in plan.steps]
        assert "tag" in step_types

    def test_resolve_with_digest(self):
        p = _profile()
        s = _stack()
        plan_no_digest = resolve(p, s)
        plan_with_digest = resolve(p, s, base_digest="sha256:abc123")
        assert plan_no_digest.artifact.fingerprint != plan_with_digest.artifact.fingerprint

    def test_resolve_includes_build_optimization(self):
        p = _profile()
        s = _stack()
        plan = resolve(p, s)
        assert plan.decision.build_optimization is not None
        assert plan.decision.build_optimization.cpu_parallelism >= 1
        build_step = next(step for step in plan.steps if step.type == "build_overlay")
        assert "STACKWARDEN_BUILD_JOBS" in build_step.build_args
        assert "--progress=plain" in build_step.buildx_flags

    def test_resolve_tuple_mode_is_explicit_and_deterministic(self, monkeypatch):
        p = _profile()
        s = _stack()
        monkeypatch.setenv("STACKWARDEN_TUPLE_LAYER_MODE", "enforce")
        plan1 = resolve(p, s, tuple_mode="off")
        monkeypatch.setenv("STACKWARDEN_TUPLE_LAYER_MODE", "warn")
        plan2 = resolve(p, s, tuple_mode="off")
        assert plan1.artifact.fingerprint == plan2.artifact.fingerprint
        assert plan1.decision.tuple_decision.get("mode") == "off"
        assert plan2.decision.tuple_decision.get("mode") == "off"
