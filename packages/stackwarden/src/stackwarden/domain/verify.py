"""Artifact integrity verification.

``verify_artifact`` performs a series of checks that prove an artifact is
valid, consistent across Docker labels / catalog / snapshot files, and that
its fingerprint can be recomputed from snapshots.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from stackwarden.domain.drift import DriftReason
from stackwarden.domain.enums import ArtifactStatus
from stackwarden.domain.hashing import fingerprint as compute_fingerprint
from stackwarden.domain.models import ArtifactRecord, Profile, StackSpec
from stackwarden.domain.snapshots import artifact_dir, load_snapshot

if TYPE_CHECKING:
    from stackwarden.catalog.store import CatalogStore
    from stackwarden.runtime.docker_client import DockerClient

log = logging.getLogger(__name__)

_REQUIRED_LABELS = [
    "stackwarden.profile",
    "stackwarden.stack",
    "stackwarden.fingerprint",
    "stackwarden.base_digest",
    "stackwarden.template_hash",
    "stackwarden.builder_version",
]


def _resolve_artifact(
    tag_or_id: str, catalog: CatalogStore,
) -> ArtifactRecord | None:
    """Look up an artifact by tag, fingerprint, or ID (in that order)."""
    record = catalog.get_artifact_by_tag(tag_or_id)
    if not record:
        record = catalog.get_artifact_by_fingerprint(tag_or_id)
    if not record:
        record = catalog.get_artifact_by_id(tag_or_id)
    return record


class VerifyErrorCode(str, Enum):
    """Structured error codes for verification failures."""
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"
    LABEL_MISSING = "label_missing"
    IMAGE_MISSING = "image_missing"
    CATALOG_MISSING = "catalog_missing"
    RECOMPUTE_DIVERGED = "recompute_diverged"
    UNKNOWN = "unknown"


class VerifyReport(BaseModel):
    ok: bool = True
    errors: list[str] = Field(default_factory=list)
    error_codes: list[VerifyErrorCode] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    facts: dict[str, str] = Field(default_factory=dict)
    recomputed_fingerprint: str | None = None
    label_fingerprint: str | None = None
    catalog_fingerprint: str | None = None


def verify_artifact(
    tag_or_id: str,
    docker_client: DockerClient,
    catalog: CatalogStore,
    *,
    strict: bool = False,
) -> VerifyReport:
    """Run all verification checks and return a structured report."""
    report = VerifyReport()

    # 1. Resolve tag/id to catalog record
    record = _resolve_artifact(tag_or_id, catalog)

    if not record:
        report.errors.append(f"No catalog record found for '{tag_or_id}'")
        report.error_codes.append(VerifyErrorCode.CATALOG_MISSING)
        report.ok = False
        return report

    if record.status != ArtifactStatus.BUILT:
        status_val = getattr(record.status, "value", str(record.status))
        report.errors.append(
            f"Verification is not applicable: artifact status is '{status_val}'. "
            "Only built artifacts can be verified (Docker image must exist)."
        )
        report.error_codes.append(VerifyErrorCode.IMAGE_MISSING)
        report.ok = False
        return report

    tag = record.tag
    report.facts["tag"] = tag
    report.facts["artifact_id"] = record.id or ""
    report.catalog_fingerprint = record.fingerprint

    # 2. Docker image exists
    if not docker_client.image_exists(tag):
        report.errors.append(f"Docker image not found: {tag}")
        report.error_codes.append(VerifyErrorCode.IMAGE_MISSING)
        report.ok = False
        return report

    # 3. Required labels (key must exist; empty string is valid e.g. template_hash when not computed)
    labels = docker_client.get_image_labels(tag)
    for label in _REQUIRED_LABELS:
        if label not in labels:
            report.errors.append(f"Missing required label: {label}")
            if VerifyErrorCode.LABEL_MISSING not in report.error_codes:
                report.error_codes.append(VerifyErrorCode.LABEL_MISSING)

    report.label_fingerprint = labels.get("stackwarden.fingerprint")

    # 4. Catalog <-> Docker consistency
    if report.label_fingerprint and report.label_fingerprint != record.fingerprint:
        report.errors.append(
            f"Fingerprint mismatch: label={report.label_fingerprint} "
            f"catalog={record.fingerprint}"
        )
        report.error_codes.append(VerifyErrorCode.FINGERPRINT_MISMATCH)

    # 5. Snapshot files exist
    art_dir = artifact_dir(record.fingerprint)
    _check_snapshot_file(report, art_dir, "profile.json", strict)
    _check_snapshot_file(report, art_dir, "stack.json", strict)
    _check_snapshot_file(report, art_dir, "manifest.json", strict)
    _check_snapshot_file(report, art_dir, "plan.json", strict)

    # 6. Recompute fingerprint from snapshots + decision inputs
    profile_path = art_dir / "profile.json"
    stack_path = art_dir / "stack.json"
    if profile_path.exists() and stack_path.exists():
        try:
            profile_data = load_snapshot(art_dir, "profile")
            stack_data = load_snapshot(art_dir, "stack")
            profile_obj = Profile.model_validate(profile_data)
            stack_obj = StackSpec.model_validate(stack_data)

            base_image = record.base_image
            base_digest = labels.get("stackwarden.base_digest") or record.base_digest
            template_hash = labels.get("stackwarden.template_hash") or record.template_hash
            builder_version = labels.get("stackwarden.builder_version", "")

            variants: dict[str, str] | None = None
            variant_label = labels.get("stackwarden.variants")
            if variant_label:
                variants = json.loads(variant_label)
            elif record.variant_json:
                variants = json.loads(record.variant_json)

            recomputed = compute_fingerprint(
                profile_obj,
                stack_obj,
                base_image,
                base_digest,
                template_hash,
                variants=variants,
                builder_version_override=builder_version or None,
            )
            report.recomputed_fingerprint = recomputed
            report.facts["recomputed_fingerprint"] = recomputed

            if report.label_fingerprint and recomputed != report.label_fingerprint:
                report.errors.append(
                    f"Recomputed fingerprint does not match label: "
                    f"recomputed={recomputed[:16]}... "
                    f"label={report.label_fingerprint[:16]}..."
                )
                if VerifyErrorCode.RECOMPUTE_DIVERGED not in report.error_codes:
                    report.error_codes.append(VerifyErrorCode.RECOMPUTE_DIVERGED)

            if recomputed != record.fingerprint:
                report.errors.append(
                    f"Recomputed fingerprint does not match catalog: "
                    f"recomputed={recomputed[:16]}... "
                    f"catalog={record.fingerprint[:16]}..."
                )
                if VerifyErrorCode.RECOMPUTE_DIVERGED not in report.error_codes:
                    report.error_codes.append(VerifyErrorCode.RECOMPUTE_DIVERGED)
        except Exception as exc:
            report.warnings.append(f"Fingerprint recompute failed: {exc}")
    else:
        report.warnings.append(
            "Cannot recompute fingerprint: profile.json or stack.json missing"
        )

    # 7. Final verdict
    if report.errors:
        report.ok = False

    return report


def apply_fix(
    tag_or_id: str,
    report: VerifyReport,
    catalog: CatalogStore,
) -> list[str]:
    """Mark the catalog record stale based on verify errors. Returns actions taken."""
    if report.ok:
        return []

    record = _resolve_artifact(tag_or_id, catalog)

    if not record:
        return ["No catalog record to fix"]

    reason = _classify_reason(report)
    record.status = ArtifactStatus.STALE
    record.stale_reason = f"verify:{reason}"
    catalog.update_artifact(record)
    return [f"Marked {record.tag} as stale (reason: verify:{reason})"]


def _classify_reason(report: VerifyReport) -> str:
    """Pick the most specific drift reason from structured error codes."""
    code_priority = [
        (VerifyErrorCode.RECOMPUTE_DIVERGED, DriftReason.FINGERPRINT_MISMATCH.value),
        (VerifyErrorCode.FINGERPRINT_MISMATCH, DriftReason.FINGERPRINT_MISMATCH.value),
        (VerifyErrorCode.LABEL_MISSING, "MISSING_LABELS"),
        (VerifyErrorCode.IMAGE_MISSING, "IMAGE_MISSING"),
        (VerifyErrorCode.CATALOG_MISSING, "CATALOG_MISSING"),
    ]
    for code, reason in code_priority:
        if code in report.error_codes:
            return reason
    return "VERIFICATION_FAILED"


def _check_snapshot_file(
    report: VerifyReport,
    art_dir: Path,
    filename: str,
    strict: bool,
) -> None:
    path = art_dir / filename
    if not path.exists():
        msg = f"Snapshot file missing: {filename}"
        if strict:
            report.errors.append(msg)
        else:
            report.warnings.append(msg)
