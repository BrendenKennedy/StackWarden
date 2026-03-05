"""Shared fixtures for StackWarden tests."""

from __future__ import annotations

import pytest

from stackwarden.domain.enums import ArtifactStatus
from stackwarden.domain.models import (
    BaseCandidate,
    CudaSpec,
    GpuSpec,
    PipDep,
    Profile,
    StackComponents,
    StackEntrypoint,
    StackSpec,
)


@pytest.fixture()
def sample_profile() -> Profile:
    return Profile.model_validate(dict(
        id="test_profile",
        display_name="Test Profile",
        arch="amd64",
        cuda=CudaSpec(major=12, minor=5, variant="cuda12.5"),
        gpu=GpuSpec(vendor="nvidia", family="ampere"),
        capabilities=["cuda", "tensor_cores"],
        base_candidates=[
            BaseCandidate(name="nvcr.io/nvidia/pytorch", tags=["24.06-py3"]),
        ],
    ))


@pytest.fixture()
def sample_stack() -> StackSpec:
    return StackSpec.model_validate(dict(
        id="test_stack",
        display_name="Test Stack",
        task="custom",
        serve="python_api",
        api="fastapi",
        build_strategy="overlay",
        components=StackComponents(
            base_role="pytorch",
            pip=[PipDep(name="fastapi", version=">=0.115")],
            apt=["curl"],
        ),
        entrypoint=StackEntrypoint(cmd=["python", "-m", "uvicorn"]),
    ))


@pytest.fixture()
def catalog_store(tmp_path):
    from stackwarden.catalog.store import CatalogStore
    return CatalogStore(db_path=tmp_path / "test_catalog.db")
