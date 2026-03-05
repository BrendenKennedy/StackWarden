"""Unit tests for stacksmith.application.create_flows module."""

from __future__ import annotations

import pytest

from stacksmith.application.create_flows import (
    AppConflictError,
    AppValidationError,
    ComposeResult,
    DryRunResult,
    build_block,
    build_profile,
    build_stack_recipe,
    compose_stack_preview,
    create_block,
    create_profile,
    create_stack,
    dry_run_block,
    dry_run_profile,
    dry_run_stack,
    normalize_profile_request,
    normalize_stack_request,
    prepare_block,
    prepare_profile,
    prepare_stack,
)
from stacksmith.domain.errors import BlockNotFoundError, ProfileNotFoundError, StackNotFoundError
from stacksmith.web.schemas import (
    BaseCandidateCreateDTO,
    BlockCreateRequest,
    CudaCreateDTO,
    GpuCreateDTO,
    ProfileCreateRequest,
    StackCreateRequest,
)


def _raise_stack_not_found(x):
    raise StackNotFoundError(x)


def _raise_block_not_found(x):
    raise BlockNotFoundError(x)


def _raise_profile_not_found(x):
    raise ProfileNotFoundError(x)


def _minimal_stack_req(**overrides) -> StackCreateRequest:
    defaults = dict(
        schema_version=3,
        id="test-stack",
        display_name="Test Stack",
        blocks=["stub-block"],
    )
    defaults.update(overrides)
    return StackCreateRequest(**defaults)


def _minimal_block_req(**overrides) -> BlockCreateRequest:
    defaults = dict(
        schema_version=1,
        id="test-block",
        display_name="Test Block",
    )
    defaults.update(overrides)
    return BlockCreateRequest(**defaults)


def _minimal_profile_req(**overrides) -> ProfileCreateRequest:
    defaults = dict(
        schema_version=1,
        id="test-profile",
        display_name="Test Profile",
        arch="amd64",
        os="linux",
        container_runtime="nvidia",
        gpu=GpuCreateDTO(vendor="nvidia", family="ampere"),
        base_candidates=[BaseCandidateCreateDTO(name="nvcr.io/nvidia/pytorch", tags=["24.06-py3"])],
    )
    defaults.update(overrides)
    return ProfileCreateRequest(**defaults)


# ---------------------------------------------------------------------------
# normalize_*_request
# ---------------------------------------------------------------------------


class TestNormalizeStackRequest:
    def test_clears_user_derived_capabilities(self):
        req = _minimal_stack_req(derived_capabilities=["cuda"])
        result = normalize_stack_request(req)
        assert "Ignored user-supplied derived_capabilities" in result.decision_trace[-1]

    def test_computes_derived_from_needs(self):
        req = _minimal_stack_req()
        req.requirements.needs = ["cuda", "tensor_cores"]
        result = normalize_stack_request(req)
        assert result.derived_capabilities == ["cuda", "tensor_cores"]
        assert any("Computed derived_capabilities" in t for t in result.decision_trace)

    def test_deduplicates_needs(self):
        req = _minimal_stack_req()
        req.requirements.needs = ["cuda", "cuda", "tensor_cores"]
        result = normalize_stack_request(req)
        assert result.derived_capabilities == ["cuda", "tensor_cores"]


class TestNormalizeProfileRequest:
    def test_clears_user_derived_capabilities(self):
        req = _minimal_profile_req(derived_capabilities=["cuda"])
        result = normalize_profile_request(req)
        assert "Ignored user-supplied derived_capabilities" in result.decision_trace[-1]


# ---------------------------------------------------------------------------
# build_* functions
# ---------------------------------------------------------------------------


class TestBuildStackRecipe:
    def test_builds_minimal_recipe(self):
        req = _minimal_stack_req(blocks=["some-block"])
        recipe = build_stack_recipe(req)
        assert recipe.id == "test-stack"
        assert recipe.display_name == "Test Stack"
        assert recipe.kind == "stack_recipe"
        assert recipe.blocks == ["some-block"]

    def test_builds_with_build_strategy(self):
        req = _minimal_stack_req(build_strategy="overlay", blocks=["some-block"])
        recipe = build_stack_recipe(req)
        assert recipe.build_strategy.value == "overlay"


class TestBuildBlock:
    def test_builds_minimal_block(self):
        req = _minimal_block_req()
        block = build_block(req)
        assert block.id == "test-block"
        assert block.kind == "block"

    def test_env_converted_to_list(self):
        req = _minimal_block_req(env={"MY_VAR": "val"})
        block = build_block(req)
        assert "MY_VAR=val" in block.env


class TestBuildProfile:
    def test_builds_minimal_profile(self):
        req = _minimal_profile_req()
        profile = build_profile(req)
        assert profile.id == "test-profile"
        assert profile.arch.value == "amd64"

    def test_cuda_optional(self):
        req = _minimal_profile_req(cuda=CudaCreateDTO(major=12, minor=5, variant="runtime"))
        profile = build_profile(req)
        assert profile.cuda is not None
        assert profile.cuda.major == 12

    def test_no_cuda(self):
        req = _minimal_profile_req()
        profile = build_profile(req)
        assert profile.cuda is None


# ---------------------------------------------------------------------------
# prepare_* functions
# ---------------------------------------------------------------------------


class TestPrepareStack:
    def test_returns_recipe_and_dict(self):
        req = _minimal_stack_req()
        recipe, payload = prepare_stack(req)
        assert recipe.id == "test-stack"
        assert isinstance(payload, dict)
        assert payload["id"] == "test-stack"


class TestPrepareBlock:
    def test_returns_block_and_dict(self):
        req = _minimal_block_req()
        block, payload = prepare_block(req)
        assert block.id == "test-block"
        assert isinstance(payload, dict)


class TestPrepareProfile:
    def test_returns_profile_and_dict(self):
        req = _minimal_profile_req()
        profile, payload = prepare_profile(req)
        assert profile.id == "test-profile"
        assert isinstance(payload, dict)


# ---------------------------------------------------------------------------
# dry_run_* functions
# ---------------------------------------------------------------------------


class TestDryRunStack:
    def test_valid_request(self):
        req = _minimal_stack_req()
        result = dry_run_stack(req)
        assert isinstance(result, DryRunResult)
        assert result.valid is True
        assert result.yaml != ""
        assert result.errors == []

    def test_invalid_id_returns_errors(self):
        req = _minimal_stack_req(id="INVALID ID")
        result = dry_run_stack(req)
        assert result.valid is False
        assert len(result.errors) > 0


class TestDryRunBlock:
    def test_valid_request(self):
        req = _minimal_block_req()
        result = dry_run_block(req)
        assert isinstance(result, DryRunResult)
        assert result.valid is True

    def test_invalid_id_returns_errors(self):
        req = _minimal_block_req(id="INVALID ID")
        result = dry_run_block(req)
        assert result.valid is False


class TestDryRunProfile:
    def test_valid_request(self):
        req = _minimal_profile_req()
        result = dry_run_profile(req)
        assert isinstance(result, DryRunResult)
        assert result.valid is True

    def test_invalid_id_returns_errors(self):
        req = _minimal_profile_req(id="INVALID ID")
        result = dry_run_profile(req)
        assert result.valid is False


# ---------------------------------------------------------------------------
# create_* functions (require filesystem)
# ---------------------------------------------------------------------------


@pytest.fixture()
def spec_dirs(tmp_path, monkeypatch):
    profiles_dir = tmp_path / "profiles"
    stacks_dir = tmp_path / "stacks"
    blocks_dir = tmp_path / "blocks"
    profiles_dir.mkdir()
    stacks_dir.mkdir()
    blocks_dir.mkdir()
    monkeypatch.setattr("stacksmith.application.create_flows.get_profiles_dir", lambda: profiles_dir)
    monkeypatch.setattr("stacksmith.application.create_flows.get_stacks_dir", lambda: stacks_dir)
    monkeypatch.setattr("stacksmith.application.create_flows.get_blocks_dir", lambda: blocks_dir)
    return {"profiles": profiles_dir, "stacks": stacks_dir, "blocks": blocks_dir}


class TestCreateStack:
    def test_creates_yaml_file(self, spec_dirs, monkeypatch):
        monkeypatch.setattr("stacksmith.application.create_flows.load_stack", _raise_stack_not_found)
        req = _minimal_stack_req()
        path = create_stack(req)
        assert path.exists()
        assert path.name == "test-stack.yaml"

    def test_conflict_raises(self, spec_dirs, monkeypatch):
        monkeypatch.setattr("stacksmith.application.create_flows.load_stack", _raise_stack_not_found)
        req = _minimal_stack_req()
        create_stack(req)
        with pytest.raises(AppConflictError):
            create_stack(req)


class TestCreateBlock:
    def test_creates_yaml_file(self, spec_dirs, monkeypatch):
        monkeypatch.setattr("stacksmith.application.create_flows.load_block", _raise_block_not_found)
        req = _minimal_block_req()
        path = create_block(req)
        assert path.exists()
        assert path.name == "test-block.yaml"


class TestCreateProfile:
    def test_creates_yaml_file(self, spec_dirs, monkeypatch):
        monkeypatch.setattr("stacksmith.application.create_flows.load_profile", _raise_profile_not_found)
        req = _minimal_profile_req()
        path = create_profile(req)
        assert path.exists()
        assert path.name == "test-profile.yaml"


# ---------------------------------------------------------------------------
# compose_stack_preview
# ---------------------------------------------------------------------------


class TestComposeStackPreview:
    def test_missing_block_returns_error(self):
        req = _minimal_stack_req(blocks=["nonexistent-block"])
        result = compose_stack_preview(req)
        assert isinstance(result, ComposeResult)
        assert result.valid is False
        assert any("compose" in e.get("field", "") for e in result.errors)
