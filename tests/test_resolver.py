"""Tests for resolver rules, scoring, and plan generation."""

import pytest

from stackwarden.domain.errors import IncompatibleStackError
from stackwarden.domain.models import (
    BaseCandidate,
    LayerSpec,
    CudaSpec,
    GpuSpec,
    HostDiscoveryFacts,
    PipDep,
    Profile,
    ProfileConstraints,
    StackComponents,
    StackEntrypoint,
    StackSpec,
)
from stackwarden.domain.tuple_catalog import SupportedTuple, TupleCatalog, TupleSelector, default_tuple_catalog
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


def _gpu_layer() -> LayerSpec:
    return LayerSpec.model_validate(
        {
            "id": "gpu_runtime",
            "display_name": "GPU Runtime",
            "stack_layer": "inference_engine_layer",
            "requires": {"gpu_vendor": "nvidia"},
        }
    )


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
        assert "STACKWARDEN_OPT_MODE" in build_step.build_args
        assert "--progress=plain" in build_step.buildx_flags

    def test_resolve_strict_host_optimization_fails_when_facts_missing(self):
        p = _profile(
            host_facts=HostDiscoveryFacts(
                cpu_cores_logical=None,
                memory_gb_total=None,
                driver_version=None,
            )
        )
        p.gpu.compute_capability = None
        s = _stack()

        with pytest.raises(IncompatibleStackError):
            resolve(
                p,
                s,
                layers=[_gpu_layer()],
                strict_host_optimization=True,
            )

    def test_resolve_strict_host_optimization_succeeds_with_facts(self):
        p = _profile(
            gpu=GpuSpec(vendor="nvidia", family="blackwell", compute_capability="12.0"),
            host_facts=HostDiscoveryFacts(
                cpu_cores_logical=32,
                memory_gb_total=128.0,
                driver_version="570.133.20",
            ),
        )
        s = _stack()
        plan = resolve(
            p,
            s,
            layers=[_gpu_layer()],
            strict_host_optimization=True,
        )
        assert plan.decision.build_optimization is not None
        assert plan.decision.build_optimization.strict_host_specific is True
        assert plan.artifact.labels.get("stackwarden.host_optimization")

    def test_resolve_strict_host_optimization_allows_curated_profile_without_host_facts(self):
        p = _profile(
            tags=["curated", "dgx", "dgx-spark"],
            labels={"optimization_scope": "curated_authoritative"},
            host_facts=HostDiscoveryFacts(
                cpu_cores_logical=None,
                memory_gb_total=None,
                driver_version=None,
            ),
        )
        p.gpu.compute_capability = None
        s = _stack()
        plan = resolve(
            p,
            s,
            layers=[_gpu_layer()],
            strict_host_optimization=True,
        )
        assert plan.decision.build_optimization is not None
        assert any(
            "Strict host-specific optimization facts missing on curated profile" in warning
            for warning in plan.decision.warnings
        )

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

    def test_default_tuple_catalog_includes_dgx_spark_cuda13(self):
        tuple_ids = {item.id for item in default_tuple_catalog().tuples}
        assert "dgx_h100_cuda125_ubuntu2204" in tuple_ids
        assert "arm_nvidia_cuda130_ubuntu2404" in tuple_ids
        assert "arm_nvidia_cuda130_ubuntu2404_pull" in tuple_ids

    def test_resolve_uses_aggressive_route_for_blackwell(self):
        p = _profile(
            arch="arm64",
            os_family="ubuntu",
            os_version="24.04",
            os_family_id="ubuntu",
            os_version_id="ubuntu_24_04",
            cuda=CudaSpec(major=13, minor=0, variant="cuda13.0"),
            gpu=GpuSpec(
                vendor="nvidia",
                family="blackwell",
                vendor_id="nvidia",
                family_id="blackwell",
                model_id="nvidia_gb10",
                compute_capability="12.1",
            ),
            host_facts=HostDiscoveryFacts(
                cpu_cores_logical=20,
                memory_gb_total=128.0,
                driver_version="570.42",
            ),
        )
        s = _stack()
        plan = resolve(
            p,
            s,
            layers=[_gpu_layer()],
            strict_host_optimization=False,
        )
        opt = plan.decision.build_optimization
        assert opt is not None
        assert opt.strategy == "aggressive"
        assert opt.policy == "strict_host_specific"
        assert opt.build_args["STACKWARDEN_OPT_PROFILE"] == "aggressive"

    def test_resolve_uses_aggressive_route_for_non_blackwell_gpu(self):
        p = _profile(
            arch="amd64",
            gpu=GpuSpec(vendor="nvidia", family="ampere", vendor_id="nvidia", family_id="ampere"),
            host_facts=HostDiscoveryFacts(
                cpu_cores_logical=8,
                memory_gb_total=32.0,
            ),
        )
        s = _stack()
        plan = resolve(p, s)
        opt = plan.decision.build_optimization
        assert opt is not None
        assert opt.strategy == "aggressive"
        assert opt.policy == "strict_host_specific"
        assert opt.build_args["STACKWARDEN_OPT_PROFILE"] == "aggressive"

    def test_resolve_uses_balanced_route_for_cpu_only_profile(self):
        p = _profile(
            arch="amd64",
            container_runtime="runc",
            cuda=None,
            gpu=GpuSpec(vendor="cpu", family="cpu"),
            host_facts=HostDiscoveryFacts(
                cpu_cores_logical=8,
                memory_gb_total=16.0,
            ),
        )
        s = _stack(task="custom", api="none", serve="custom")
        plan = resolve(p, s)
        opt = plan.decision.build_optimization
        assert opt is not None
        assert opt.strategy == "balanced"
        assert opt.policy == "portable"
        assert opt.build_args["STACKWARDEN_OPT_PROFILE"] == "balanced"

    def test_resolve_emits_workload_policy_knobs(self):
        p = _profile(
            arch="amd64",
            gpu=GpuSpec(vendor="nvidia", family="hopper", vendor_id="nvidia", family_id="hopper"),
            host_facts=HostDiscoveryFacts(
                cpu_cores_logical=12,
                memory_gb_total=48.0,
            ),
        )
        s = _stack(task="llm", api="fastapi", serve="python_api")
        plan = resolve(p, s, layers=[_gpu_layer()])
        step = next(step for step in plan.steps if step.type == "build_overlay")
        assert step.build_args["STACKWARDEN_OPT_WORKLOAD"] == "llm"
        assert step.build_args["STACKWARDEN_OPT_SERVING"] == "fastapi"
        assert step.build_args["STACKWARDEN_BATCH_PROFILE"] == "throughput_high"
        assert step.build_args["STACKWARDEN_CUDA_GRAPH"] == "hybrid"
        assert step.build_args["STACKWARDEN_PREFILL_POLICY"] == "none"

    def test_resolve_applies_tuple_base_and_wheelhouse_hints(self):
        p = _profile(
            arch="arm64",
            os_family="ubuntu",
            os_version="24.04",
            os_family_id="ubuntu",
            os_version_id="ubuntu_24_04",
            cuda=CudaSpec(major=13, minor=0, variant="cuda13.0"),
            gpu=GpuSpec(vendor="nvidia", family="blackwell", vendor_id="nvidia", family_id="blackwell"),
        )
        s = _stack()
        tuples = TupleCatalog(
            tuples=[
                SupportedTuple(
                    id="dgx_hint",
                    status="supported",
                    selector=TupleSelector(
                        arch="arm64",
                        os_family_id="ubuntu",
                        os_version_id="ubuntu_24_04",
                        container_runtime="nvidia",
                        gpu_vendor_id="nvidia",
                        gpu_family_id="blackwell",
                        cuda_min=13.0,
                        cuda_max=13.0,
                    ),
                    base_image="nvcr.io/nvidia/pytorch:25.03-py3",
                    wheelhouse_path="/opt/wheelhouse/dgx",
                )
            ]
        )
        plan = resolve(
            p,
            s,
            tuple_mode="warn",
            tuple_catalog=tuples,
        )
        assert plan.decision.base_image == "nvcr.io/nvidia/pytorch:25.03-py3"
        build_step = next(step for step in plan.steps if step.type == "build_overlay")
        assert build_step.build_args["STACKWARDEN_PIP_WHEELHOUSE_PATH_HINT"] == "/opt/wheelhouse/dgx"
        assert plan.artifact.labels["stackwarden.tuple_base_image_hint"] == "nvcr.io/nvidia/pytorch:25.03-py3"
