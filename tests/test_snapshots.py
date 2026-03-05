"""Tests for spec snapshot persistence and canonical JSON stability."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from stacksmith.domain.hashing import canonical_json
from stacksmith.domain.models import (
    BaseCandidate,
    CudaSpec,
    GpuSpec,
    PipDep,
    Plan,
    PlanArtifact,
    PlanDecision,
    PlanStep,
    Profile,
    StackComponents,
    StackEntrypoint,
    StackSpec,
)
from stacksmith.domain.snapshots import artifact_dir, load_snapshot, write_snapshot_files


def _profile() -> Profile:
    return Profile.model_validate(dict(
        id="test_profile",
        display_name="Test",
        arch="arm64",
        cuda=CudaSpec(major=12, minor=5, variant="cuda12.5"),
        gpu=GpuSpec(vendor="nvidia", family="test"),
        base_candidates=[BaseCandidate(name="pytorch", tags=["latest"])],
    ))


def _stack() -> StackSpec:
    return StackSpec.model_validate(dict(
        id="test_stack",
        display_name="Test",
        task="diffusion",
        serve="python_api",
        api="fastapi",
        build_strategy="overlay",
        components=StackComponents(
            base_role="pytorch",
            pip=[PipDep(name="fastapi", version="==0.115.*")],
            apt=["git"],
        ),
        env=["PYTHONUNBUFFERED=1"],
        ports=[8000],
        entrypoint=StackEntrypoint(cmd=["python", "main.py"]),
    ))


def _plan() -> Plan:
    return Plan(
        plan_id="plan_test",
        profile_id="test_profile",
        stack_id="test_stack",
        decision=PlanDecision(base_image="pytorch:latest", builder="overlay"),
        steps=[PlanStep(type="pull", image="pytorch:latest")],
        artifact=PlanArtifact(tag="local/stacksmith:test", fingerprint="abc123"),
    )


class TestArtifactDir:
    def test_returns_path_under_artifacts_root(self, tmp_path):
        fp = "abcdef1234567890"
        with patch("stacksmith.domain.snapshots.get_artifacts_root", return_value=tmp_path):
            result = artifact_dir(fp)
            assert result == tmp_path / fp


class TestCanonicalJson:
    def test_sorted_keys(self):
        result = canonical_json({"z": 1, "a": 2, "m": 3})
        assert result == '{"a":2,"m":3,"z":1}'

    def test_compact_separators(self):
        result = canonical_json({"key": "value"})
        assert " " not in result

    def test_deterministic(self):
        data = {"b": [3, 1, 2], "a": "hello"}
        assert canonical_json(data) == canonical_json(data)


class TestWriteSnapshotFiles:
    def test_writes_profile_and_stack(self, tmp_path):
        profile = _profile()
        stack = _stack()
        paths = write_snapshot_files(tmp_path, profile, stack)

        assert "profile_snapshot_path" in paths
        assert "stack_snapshot_path" in paths
        assert (tmp_path / "profile.json").exists()
        assert (tmp_path / "stack.json").exists()

    def test_writes_plan_when_provided(self, tmp_path):
        paths = write_snapshot_files(tmp_path, _profile(), _stack(), _plan())
        assert "plan_path" in paths
        assert (tmp_path / "plan.json").exists()

    def test_no_plan_when_omitted(self, tmp_path):
        paths = write_snapshot_files(tmp_path, _profile(), _stack())
        assert "plan_path" not in paths
        assert not (tmp_path / "plan.json").exists()

    def test_canonical_json_format(self, tmp_path):
        profile = _profile()
        write_snapshot_files(tmp_path, profile, _stack())
        raw = (tmp_path / "profile.json").read_text()
        expected = canonical_json(profile.model_dump(mode="json"))
        assert raw == expected

    def test_round_trip_profile(self, tmp_path):
        profile = _profile()
        write_snapshot_files(tmp_path, profile, _stack())
        loaded = load_snapshot(tmp_path, "profile")
        reconstructed = Profile.model_validate(loaded)
        assert reconstructed.id == profile.id
        assert reconstructed.arch == profile.arch
        assert reconstructed.cuda.variant == profile.cuda.variant

    def test_round_trip_stack(self, tmp_path):
        stack = _stack()
        write_snapshot_files(tmp_path, _profile(), stack)
        loaded = load_snapshot(tmp_path, "stack")
        reconstructed = StackSpec.model_validate(loaded)
        assert reconstructed.id == stack.id
        assert reconstructed.task == stack.task
        assert len(reconstructed.components.pip) == len(stack.components.pip)

    def test_creates_directory(self, tmp_path):
        nested = tmp_path / "sub" / "dir"
        write_snapshot_files(nested, _profile(), _stack())
        assert nested.exists()

    def test_idempotent(self, tmp_path):
        profile = _profile()
        stack = _stack()
        write_snapshot_files(tmp_path, profile, stack)
        content1 = (tmp_path / "profile.json").read_text()
        write_snapshot_files(tmp_path, profile, stack)
        content2 = (tmp_path / "profile.json").read_text()
        assert content1 == content2
