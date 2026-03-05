"""Integration test: build a trivial overlay on python:3.12-slim.

Skipped if Docker is not available.
"""


import pytest

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

import importlib.util


def _docker_available() -> bool:
    if importlib.util.find_spec("docker") is None:
        return False
    try:
        import docker
        client = docker.from_env()
        client.ping()
        client.close()
        return True
    except Exception:
        return False


DOCKER_AVAILABLE = _docker_available()

pytestmark = pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available")


@pytest.fixture(autouse=True)
def _tuple_layer_off(monkeypatch):
    """Trivial profile (arm64, cpu) does not match any tuple; disable for build tests."""
    monkeypatch.setenv("STACKWARDEN_TUPLE_LAYER_MODE", "off")


def _trivial_profile() -> Profile:
    return Profile.model_validate(dict(
        id="integration_test",
        display_name="Integration Test",
        arch="arm64",
        cuda=CudaSpec(major=0, minor=0, variant="none"),
        gpu=GpuSpec(vendor="none", family="none"),
        capabilities=[],
        base_candidates=[BaseCandidate(name="python", tags=["3.12-slim"])],
    ))


def _trivial_stack() -> StackSpec:
    return StackSpec.model_validate(dict(
        id="integration_test",
        display_name="Integration Test Stack",
        task="custom",
        serve="custom",
        api="none",
        build_strategy="overlay",
        components=StackComponents(
            base_role="python",
            pip=[PipDep(name="six", version=">=1.16")],
        ),
        entrypoint=StackEntrypoint(cmd=["python", "-c", "print('hello')"]),
    ))


class TestOverlayBuild:
    def test_build_and_catalog(self, tmp_path):
        from stackwarden.catalog.store import CatalogStore
        from stackwarden.resolvers.resolver import resolve
        from stackwarden.builders.plan_executor import execute_plan
        from stackwarden.runtime.docker_client import DockerClient

        profile = _trivial_profile()
        stack = _trivial_stack()
        plan = resolve(profile, stack)
        assert plan.decision.build_optimization is not None
        assert "stackwarden.build_optimization" in plan.artifact.labels

        catalog = CatalogStore(tmp_path / "test.db")
        catalog.upsert_profile(profile)
        catalog.upsert_stack(stack)

        docker = DockerClient()
        record = execute_plan(plan, profile, stack, docker, catalog)

        assert record.status.value == "built"
        assert record.tag == plan.artifact.tag

        assert docker.image_exists(plan.artifact.tag)

        labels = docker.get_image_labels(plan.artifact.tag)
        assert labels.get("stackwarden.fingerprint") == plan.artifact.fingerprint
        assert labels.get("stackwarden.profile") == "integration_test"
        assert labels.get("stackwarden.stack") == "integration_test"

        cat_record = catalog.get_artifact_by_tag(plan.artifact.tag)
        assert cat_record is not None
        assert cat_record.status.value == "built"
