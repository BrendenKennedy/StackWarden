"""Drift detection unit tests — all 6 drift rules."""

from __future__ import annotations

import pytest

from stacksmith.domain.drift import DriftReason, detect_drift, drift_summary, is_stale
from stacksmith.domain.enums import ArtifactStatus
from stacksmith.domain.models import (
    ArtifactRecord,
    Plan,
    PlanArtifact,
    PlanDecision,
)
from stacksmith import __version__


def _plan(fp: str = "abc123", base_digest: str = "sha256:aaa", tmpl_hash: str = "t1",
          schema_version: str = "1") -> Plan:
    return Plan(
        plan_id="test",
        profile_id="p1",
        stack_id="s1",
        decision=PlanDecision(
            base_image="nvcr.io/nvidia/pytorch:24.06",
            base_digest=base_digest,
            builder="overlay",
        ),
        steps=[],
        artifact=PlanArtifact(
            tag="local/stacksmith:test",
            fingerprint=fp,
            labels={
                "stacksmith.fingerprint": fp,
                "stacksmith.base_digest": base_digest,
                "stacksmith.template_hash": tmpl_hash,
                "stacksmith.schema_version": schema_version,
                "stacksmith.builder_version": __version__,
            },
        ),
    )


def _record(**overrides) -> ArtifactRecord:
    defaults = dict(
        id="r1", profile_id="p1", stack_id="s1",
        tag="local/stacksmith:test", fingerprint="abc123",
        base_image="nvcr.io/nvidia/pytorch:24.06",
        build_strategy="overlay", stack_schema_version=1,
        status=ArtifactStatus.BUILT,
    )
    defaults.update(overrides)
    return ArtifactRecord(**defaults)


class TestDetectDrift:
    def test_no_drift(self):
        plan = _plan()
        labels = dict(plan.artifact.labels)
        reasons = detect_drift(labels, _record(), plan)
        assert reasons == []
        assert not is_stale(reasons)

    def test_fingerprint_mismatch(self):
        plan = _plan(fp="abc123")
        labels = {**plan.artifact.labels, "stacksmith.fingerprint": "different"}
        reasons = detect_drift(labels, _record(), plan)
        assert DriftReason.FINGERPRINT_MISMATCH in reasons

    def test_base_digest_changed(self):
        plan = _plan(base_digest="sha256:aaa")
        labels = {**plan.artifact.labels, "stacksmith.base_digest": "sha256:bbb"}
        reasons = detect_drift(labels, _record(), plan)
        assert DriftReason.BASE_DIGEST_CHANGED in reasons

    def test_template_hash_changed(self):
        plan = _plan(tmpl_hash="t1")
        labels = {**plan.artifact.labels, "stacksmith.template_hash": "t2"}
        reasons = detect_drift(labels, _record(), plan)
        assert DriftReason.TEMPLATE_HASH_CHANGED in reasons

    def test_schema_version_changed(self):
        plan = _plan(schema_version="2")
        labels = {**plan.artifact.labels, "stacksmith.schema_version": "1"}
        reasons = detect_drift(labels, _record(), plan)
        assert DriftReason.STACK_SCHEMA_CHANGED in reasons

    def test_builder_version_changed(self):
        plan = _plan()
        labels = {**plan.artifact.labels, "stacksmith.builder_version": "0.0.0"}
        reasons = detect_drift(labels, _record(), plan)
        assert DriftReason.BUILDER_VERSION_CHANGED in reasons

    def test_multiple_drift(self):
        plan = _plan()
        labels = {
            **plan.artifact.labels,
            "stacksmith.fingerprint": "wrong",
            "stacksmith.builder_version": "0.0.0",
        }
        reasons = detect_drift(labels, _record(), plan)
        assert len(reasons) >= 2

    def test_empty_labels_detected_as_drift(self):
        """An image with no stacksmith labels at all must report drift."""
        plan = _plan()
        reasons = detect_drift({}, _record(), plan)
        assert DriftReason.LABELS_MISSING in reasons
        assert is_stale(reasons)

    def test_non_stacksmith_labels_detected_as_drift(self):
        """Labels present but none with stacksmith prefix must report drift."""
        plan = _plan()
        reasons = detect_drift({"maintainer": "someone"}, _record(), plan)
        assert DriftReason.LABELS_MISSING in reasons

    def test_missing_fingerprint_label_is_mismatch(self):
        """If fingerprint label is absent but other stacksmith labels exist."""
        plan = _plan()
        labels = {
            "stacksmith.profile": "p1",
            "stacksmith.stack": "s1",
            "stacksmith.builder_version": __version__,
        }
        reasons = detect_drift(labels, _record(), plan)
        assert DriftReason.FINGERPRINT_MISMATCH in reasons

    def test_drift_summary(self):
        reasons = [DriftReason.FINGERPRINT_MISMATCH, DriftReason.BASE_DIGEST_CHANGED]
        s = drift_summary(reasons)
        assert "fingerprint_mismatch" in s
        assert "base_digest_changed" in s
