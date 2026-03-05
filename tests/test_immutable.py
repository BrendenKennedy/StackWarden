"""Immutable mode tests — ensure --immutable fails on drift, succeeds on match."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from stackwarden.domain.drift import DriftReason
from stackwarden.domain.enums import ArtifactStatus
from stackwarden.domain.errors import DriftError
from stackwarden.domain.models import (
    ArtifactRecord,
    Plan,
    PlanArtifact,
    PlanDecision,
)
from stackwarden.builders.plan_executor import check_existing
from stackwarden import __version__


def _plan(fp: str = "abc123") -> Plan:
    return Plan(
        plan_id="test",
        profile_id="p1",
        stack_id="s1",
        decision=PlanDecision(
            base_image="base:latest",
            base_digest="sha256:aaa",
            builder="overlay",
        ),
        steps=[],
        artifact=PlanArtifact(
            tag="local/stackwarden:test",
            fingerprint=fp,
            labels={
                "stackwarden.fingerprint": fp,
                "stackwarden.base_digest": "sha256:aaa",
                "stackwarden.template_hash": "",
                "stackwarden.schema_version": "1",
                "stackwarden.builder_version": __version__,
            },
        ),
    )


def _record(**overrides) -> ArtifactRecord:
    defaults = dict(
        id="r1", profile_id="p1", stack_id="s1",
        tag="local/stackwarden:test", fingerprint="abc123",
        base_image="base:latest",
        build_strategy="overlay", stack_schema_version=1,
        status=ArtifactStatus.BUILT,
    )
    defaults.update(overrides)
    return ArtifactRecord(**defaults)


class TestImmutableMode:
    def test_drift_error_is_a_stackwarden_error(self):
        from stackwarden.domain.errors import StackWardenError
        err = DriftError("tag", "reason")
        assert isinstance(err, StackWardenError)
        assert "tag" in str(err)
        assert "reason" in str(err)

    def test_drift_error_message(self):
        err = DriftError("local/stackwarden:test", "fingerprint_mismatch")
        assert "Immutable mode" in str(err)
        assert "fingerprint_mismatch" in str(err)

    def test_immutable_raises_on_drift(self):
        """When --immutable and drift is detected, DriftError must be raised."""
        plan = _plan()
        docker = MagicMock()
        docker.image_exists.return_value = True
        docker.get_image_labels.return_value = {
            **plan.artifact.labels,
            "stackwarden.fingerprint": "WRONG",
        }
        catalog = MagicMock()
        catalog.get_artifact_by_tag.return_value = _record()

        with pytest.raises(DriftError):
            check_existing(plan, docker, catalog, immutable=True)

    def test_immutable_succeeds_when_no_drift(self):
        """When --immutable and image matches, return the record."""
        plan = _plan()
        docker = MagicMock()
        docker.image_exists.return_value = True
        docker.get_image_labels.return_value = dict(plan.artifact.labels)
        record = _record()
        catalog = MagicMock()
        catalog.get_artifact_by_tag.return_value = record

        result = check_existing(plan, docker, catalog, immutable=True)
        assert result is not None
        assert result.fingerprint == plan.artifact.fingerprint

    def test_immutable_raises_when_image_missing_but_catalog_exists(self):
        """When --immutable, image gone but catalog has it as BUILT, raise."""
        plan = _plan()
        docker = MagicMock()
        docker.image_exists.return_value = False
        catalog = MagicMock()
        catalog.get_artifact_by_tag.return_value = _record()

        with pytest.raises(DriftError):
            check_existing(plan, docker, catalog, immutable=True)

    def test_non_immutable_returns_none_on_drift(self):
        """Without --immutable, drift returns None (triggers rebuild)."""
        plan = _plan()
        docker = MagicMock()
        docker.image_exists.return_value = True
        docker.get_image_labels.return_value = {
            **plan.artifact.labels,
            "stackwarden.fingerprint": "WRONG",
        }
        record = _record()
        catalog = MagicMock()
        catalog.get_artifact_by_tag.return_value = record

        result = check_existing(plan, docker, catalog, immutable=False)
        assert result is None
