"""Tests for artifact verification logic."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from stackwarden.domain.enums import ArtifactStatus
from stackwarden.domain.hashing import canonical_json, fingerprint
from stackwarden.domain.models import (
    ArtifactRecord,
    BaseCandidate,
    CudaSpec,
    GpuSpec,
    PipDep,
    Profile,
    StackComponents,
    StackEntrypoint,
    StackSpec,
)
from stackwarden.domain.snapshots import write_snapshot_files
from stackwarden.domain.verify import VerifyReport, apply_fix, verify_artifact


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
        components=StackComponents(base_role="pytorch"),
        entrypoint=StackEntrypoint(cmd=["python"]),
    ))


def _make_record(fp: str, tag: str = "local/stackwarden:test") -> ArtifactRecord:
    return ArtifactRecord(
        id="art1",
        profile_id="test_profile",
        stack_id="test_stack",
        tag=tag,
        fingerprint=fp,
        base_image="pytorch:latest",
        base_digest="sha256:abc",
        build_strategy="overlay",
        template_hash="tmpl_hash_1",
        status=ArtifactStatus.BUILT,
    )


class TestVerifyReport:
    def test_default_ok(self):
        r = VerifyReport()
        assert r.ok is True
        assert r.errors == []
        assert r.warnings == []


class TestVerifyArtifact:
    def test_no_catalog_record(self):
        docker = MagicMock()
        catalog = MagicMock()
        catalog.get_artifact_by_tag.return_value = None
        catalog.get_artifact_by_fingerprint.return_value = None
        catalog.get_artifact_by_id.return_value = None

        report = verify_artifact("nonexistent", docker, catalog)
        assert not report.ok
        assert any("No catalog record" in e for e in report.errors)

    def test_failed_artifact_not_applicable(self):
        """Verify returns early with friendly message for failed/stale artifacts (no Docker image)."""
        record = _make_record("fp123")
        record.status = ArtifactStatus.FAILED
        docker = MagicMock()
        catalog = MagicMock()
        catalog.get_artifact_by_tag.return_value = record
        catalog.get_artifact_by_fingerprint.return_value = None
        catalog.get_artifact_by_id.return_value = None

        report = verify_artifact("local/stackwarden:test", docker, catalog)
        assert not report.ok
        assert any("not applicable" in e.lower() for e in report.errors)
        assert any("failed" in e.lower() or "status" in e.lower() for e in report.errors)
        docker.image_exists.assert_not_called()

    def test_image_not_found(self):
        record = _make_record("fp123")
        docker = MagicMock()
        docker.image_exists.return_value = False
        catalog = MagicMock()
        catalog.get_artifact_by_tag.return_value = record

        report = verify_artifact("local/stackwarden:test", docker, catalog)
        assert not report.ok
        assert any("Docker image not found" in e for e in report.errors)

    def test_missing_labels(self):
        record = _make_record("fp123")
        docker = MagicMock()
        docker.image_exists.return_value = True
        docker.get_image_labels.return_value = {}
        catalog = MagicMock()
        catalog.get_artifact_by_tag.return_value = record

        with patch("stackwarden.domain.verify.artifact_dir") as mock_ad:
            mock_ad.return_value = MagicMock()
            mock_ad.return_value.__truediv__ = lambda self, x: MagicMock(exists=lambda: False)
            report = verify_artifact("local/stackwarden:test", docker, catalog)

        assert not report.ok
        assert any("Missing required label" in e for e in report.errors)

    def test_fingerprint_mismatch_label_vs_catalog(self):
        record = _make_record("fp_catalog")
        docker = MagicMock()
        docker.image_exists.return_value = True
        docker.get_image_labels.return_value = {
            "stackwarden.profile": "p",
            "stackwarden.stack": "s",
            "stackwarden.fingerprint": "fp_label_different",
            "stackwarden.base_digest": "sha256:abc",
            "stackwarden.template_hash": "th",
            "stackwarden.builder_version": "0.1.0",
        }
        catalog = MagicMock()
        catalog.get_artifact_by_tag.return_value = record

        with patch("stackwarden.domain.verify.artifact_dir") as mock_ad:
            mock_dir = MagicMock()
            mock_dir.__truediv__ = lambda self, x: MagicMock(exists=lambda: False)
            mock_ad.return_value = mock_dir
            report = verify_artifact("local/stackwarden:test", docker, catalog)

        assert not report.ok
        assert any("Fingerprint mismatch" in e for e in report.errors)

    def test_strict_mode_requires_plan_json(self, tmp_path):
        profile = _profile()
        stack = _stack()
        fp = fingerprint(profile, stack, "pytorch:latest", "sha256:abc", "th", builder_version_override="0.1.0")
        record = _make_record(fp)
        record.base_digest = "sha256:abc"
        record.template_hash = "th"

        art_dir = tmp_path / fp
        write_snapshot_files(art_dir, profile, stack)
        (art_dir / "manifest.json").write_text("{}")

        docker = MagicMock()
        docker.image_exists.return_value = True
        docker.get_image_labels.return_value = {
            "stackwarden.profile": "test_profile",
            "stackwarden.stack": "test_stack",
            "stackwarden.fingerprint": fp,
            "stackwarden.base_digest": "sha256:abc",
            "stackwarden.template_hash": "th",
            "stackwarden.builder_version": "0.1.0",
        }
        catalog = MagicMock()
        catalog.get_artifact_by_tag.return_value = record

        with patch("stackwarden.domain.verify.artifact_dir", return_value=art_dir):
            report = verify_artifact("local/stackwarden:test", docker, catalog, strict=True)

        plan_errors = [e for e in report.errors if "plan.json" in e]
        assert len(plan_errors) == 1

    def test_happy_path_recompute(self, tmp_path):
        profile = _profile()
        stack = _stack()
        fp = fingerprint(profile, stack, "pytorch:latest", "sha256:abc", "th", builder_version_override="0.1.0")
        record = _make_record(fp)
        record.base_digest = "sha256:abc"
        record.template_hash = "th"

        art_dir = tmp_path / fp
        write_snapshot_files(art_dir, profile, stack)
        (art_dir / "manifest.json").write_text("{}")
        (art_dir / "plan.json").write_text("{}")

        docker = MagicMock()
        docker.image_exists.return_value = True
        docker.get_image_labels.return_value = {
            "stackwarden.profile": "test_profile",
            "stackwarden.stack": "test_stack",
            "stackwarden.fingerprint": fp,
            "stackwarden.base_digest": "sha256:abc",
            "stackwarden.template_hash": "th",
            "stackwarden.builder_version": "0.1.0",
        }
        catalog = MagicMock()
        catalog.get_artifact_by_tag.return_value = record

        with patch("stackwarden.domain.verify.artifact_dir", return_value=art_dir):
            report = verify_artifact("local/stackwarden:test", docker, catalog, strict=True)

        assert report.ok
        assert report.recomputed_fingerprint == fp


class TestApplyFix:
    def test_fix_marks_stale(self):
        from stackwarden.domain.verify import VerifyErrorCode
        record = _make_record("fp123")
        catalog = MagicMock()
        catalog.get_artifact_by_tag.return_value = record

        report = VerifyReport(
            ok=False,
            errors=["Recomputed fingerprint does not match label"],
            error_codes=[VerifyErrorCode.RECOMPUTE_DIVERGED],
        )
        actions = apply_fix("local/stackwarden:test", report, catalog)

        assert len(actions) == 1
        assert "stale" in actions[0].lower()
        catalog.update_artifact.assert_called_once()
        updated = catalog.update_artifact.call_args[0][0]
        assert updated.status == ArtifactStatus.STALE
        assert updated.stale_reason.startswith("verify:")

    def test_fix_noop_when_ok(self):
        report = VerifyReport(ok=True)
        catalog = MagicMock()
        actions = apply_fix("tag", report, catalog)
        assert actions == []
        catalog.update_artifact.assert_not_called()

    def test_fix_reason_string_format(self):
        from stackwarden.domain.verify import VerifyErrorCode
        record = _make_record("fp123")
        catalog = MagicMock()
        catalog.get_artifact_by_tag.return_value = record

        report = VerifyReport(
            ok=False,
            errors=["Recomputed fingerprint does not match catalog"],
            error_codes=[VerifyErrorCode.RECOMPUTE_DIVERGED],
        )
        apply_fix("local/stackwarden:test", report, catalog)
        updated = catalog.update_artifact.call_args[0][0]
        assert updated.stale_reason == "verify:fingerprint_mismatch"
