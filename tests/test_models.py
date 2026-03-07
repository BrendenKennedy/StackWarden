"""Tests for domain model parsing and validation."""

import pytest
from pydantic import ValidationError

from stackwarden.domain.enums import (
    ApiType,
    Arch,
    ArtifactStatus,
    BuildStrategy,
    ContainerRuntime,
    ServeType,
    TaskType,
)
from stackwarden.domain.models import (
    ArtifactRecord,
    BaseCandidate,
    LayerSpec,
    CudaSpec,
    GpuSpec,
    Plan,
    PlanArtifact,
    PlanDecision,
    PlanStep,
    Profile,
    ProfileDefaults,
    StackRecipeSpec,
    StackSpec,
)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def _make_profile(**overrides) -> Profile:
    defaults = dict(
        schema_version=1,
        id="test_profile",
        display_name="Test Profile",
        arch="arm64",
        os="linux",
        container_runtime="nvidia",
        cuda=CudaSpec(major=12, minor=5, variant="cuda12.5"),
        gpu=GpuSpec(vendor="nvidia", family="test"),
        capabilities=["cuda"],
        base_candidates=[BaseCandidate(name="nvcr.io/nvidia/pytorch", tags=["24.06-py3"])],
        defaults=ProfileDefaults(),
    )
    defaults.update(overrides)
    return Profile(**defaults)


class TestProfile:
    def test_parse_minimal(self):
        p = _make_profile()
        assert p.id == "test_profile"
        assert p.arch == Arch.ARM64
        assert p.cuda.major == 12
        assert len(p.base_candidates) == 1

    def test_parse_from_yaml(self, tmp_path):
        yaml_content = {
            "schema_version": 1,
            "id": "yaml_test",
            "display_name": "YAML Test",
            "arch": "amd64",
            "os": "linux",
            "container_runtime": "runc",
            "cuda": {"major": 11, "minor": 8, "variant": "cuda11.8"},
            "gpu": {"vendor": "nvidia", "family": "ampere"},
            "base_candidates": [
                {"name": "pytorch/pytorch", "tags": ["2.0-cuda11.8"]}
            ],
        }
        p = Profile.model_validate(yaml_content)
        assert p.arch == Arch.AMD64
        assert p.container_runtime == ContainerRuntime.RUNC

    def test_invalid_arch_rejected(self):
        with pytest.raises(ValidationError):
            _make_profile(arch="mips64")

    def test_defaults_applied(self):
        p = _make_profile()
        assert p.defaults.python == "3.10"
        assert p.defaults.workdir == "/workspace"

    def test_constraints_default_empty(self):
        p = _make_profile()
        assert p.constraints.disallow == {}
        assert p.constraints.require == {}


# ---------------------------------------------------------------------------
# StackSpec
# ---------------------------------------------------------------------------


def _make_stack(**overrides) -> StackSpec:
    defaults = dict(
        id="test_stack",
        display_name="Test Stack",
        task="diffusion",
        serve="python_api",
        api="fastapi",
        build_strategy="overlay",
        components={"base_role": "pytorch", "pip": [{"name": "fastapi", "version": "==0.115.*"}]},
        entrypoint={"cmd": ["python", "main.py"]},
    )
    defaults.update(overrides)
    return StackSpec.model_validate(defaults)


class TestStackSpec:
    def test_parse_minimal(self):
        s = _make_stack()
        assert s.task == TaskType.DIFFUSION
        assert s.serve == ServeType.PYTHON_API
        assert s.api == ApiType.FASTAPI
        assert s.build_strategy == BuildStrategy.OVERLAY

    def test_pip_deps_parsed(self):
        s = _make_stack()
        assert len(s.components.pip) == 1
        assert s.components.pip[0].name == "fastapi"
        assert s.components.pip[0].version_mode == "custom"

    def test_npm_deps_parsed(self):
        s = _make_stack(
            components={
                "base_role": "pytorch",
                "npm": [{"name": "next", "version_mode": "latest"}],
            },
        )
        assert len(s.components.npm) == 1
        assert s.components.npm[0].name == "next"

    def test_invalid_task_rejected(self):
        with pytest.raises(ValidationError):
            _make_stack(task="quantum_computing")

    def test_empty_env_ports(self):
        s = _make_stack()
        assert s.env == []
        assert s.ports == []

    def test_files_copy_alias(self):
        s = _make_stack(files={"copy": [{"src": "app/", "dst": "/app"}]})
        assert len(s.files.copy_items) == 1
        assert s.files.copy_items[0].src == "app/"

    def test_kind_default_is_stack(self):
        s = _make_stack()
        assert s.kind == "stack"

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValidationError):
            _make_stack(kind="not_a_kind")

    def test_pin_only_requires_constraints_for_all_apt(self):
        with pytest.raises(ValidationError):
            _make_stack(
                components={
                    "base_role": "pytorch",
                    "apt": ["curl", "git"],
                    "apt_constraints": {"curl": "=8.5.0-1ubuntu1"},
                    "apt_install_mode": "pin_only",
                }
            )

    def test_lock_only_requires_lockfile_copy(self):
        with pytest.raises(ValidationError):
            _make_stack(
                components={
                    "base_role": "pytorch",
                    "npm_install_mode": "lock_only",
                },
                files={"copy": []},
            )


class TestLayerSpec:
    def test_parse_minimal(self):
        layer = LayerSpec.model_validate({
            "kind": "layer",
            "id": "fastapi",
            "display_name": "FastAPI",
            "stack_layer": "serving_layer",
        })
        assert layer.kind == "layer"
        assert layer.id == "fastapi"

    def test_missing_kind_uses_default(self):
        layer = LayerSpec.model_validate({
            "id": "runtime",
            "display_name": "Runtime",
            "stack_layer": "inference_engine_layer",
        })
        assert layer.kind == "layer"


class TestStackRecipeSpec:
    def test_parse_minimal(self):
        recipe = StackRecipeSpec.model_validate({
            "kind": "stack_recipe",
            "id": "composed",
            "display_name": "Composed",
            "task": "llm",
            "serve": "python_api",
            "api": "fastapi",
            "layers": ["fastapi"],
        })
        assert recipe.kind == "stack_recipe"
        assert recipe.layers == ["fastapi"]

    def test_rejects_empty_layers(self):
        with pytest.raises(ValidationError):
            StackRecipeSpec.model_validate({
                "kind": "stack_recipe",
                "id": "composed",
                "display_name": "Composed",
                "task": "llm",
                "serve": "python_api",
                "api": "fastapi",
                "layers": [],
            })

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValidationError):
            StackRecipeSpec.model_validate({
                "kind": "stack",
                "id": "composed",
                "display_name": "Composed",
                "task": "llm",
                "serve": "python_api",
                "api": "fastapi",
                "layers": ["fastapi"],
            })


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


class TestPlan:
    def test_plan_round_trip_json(self):
        plan = Plan(
            plan_id="plan_test",
            profile_id="dgx_spark",
            stack_id="diffusion_fastapi",
            decision=PlanDecision(base_image="pytorch:latest", builder="overlay"),
            steps=[PlanStep(type="pull", image="pytorch:latest")],
            artifact=PlanArtifact(
                tag="local/stackwarden:test",
                fingerprint="abc123",
                labels={"stackwarden.profile": "dgx_spark"},
            ),
        )
        data = plan.to_json()
        assert data["plan_id"] == "plan_test"
        assert data["artifact"]["labels"]["stackwarden.profile"] == "dgx_spark"

    def test_plan_artifact_labels_present(self):
        plan = Plan(
            plan_id="plan_labels",
            profile_id="p",
            stack_id="s",
            decision=PlanDecision(base_image="base", builder="overlay"),
            steps=[],
            artifact=PlanArtifact(
                tag="tag",
                fingerprint="fp",
                labels={
                    "stackwarden.profile": "p",
                    "stackwarden.stack": "s",
                    "stackwarden.fingerprint": "fp",
                    "stackwarden.base_digest": "",
                    "stackwarden.schema_version": "1",
                },
            ),
        )
        assert len(plan.artifact.labels) == 5


# ---------------------------------------------------------------------------
# ArtifactRecord
# ---------------------------------------------------------------------------


class TestArtifactRecord:
    def test_status_lifecycle(self):
        rec = ArtifactRecord(
            profile_id="p", stack_id="s", tag="t", fingerprint="fp",
            base_image="base", build_strategy="overlay",
            status=ArtifactStatus.PLANNED,
        )
        assert rec.status == ArtifactStatus.PLANNED
        rec.status = ArtifactStatus.BUILDING
        assert rec.status == ArtifactStatus.BUILDING
        rec.status = ArtifactStatus.BUILT
        assert rec.status == ArtifactStatus.BUILT

    def test_five_states_exist(self):
        states = {s.value for s in ArtifactStatus}
        assert states == {"planned", "building", "built", "failed", "stale"}
