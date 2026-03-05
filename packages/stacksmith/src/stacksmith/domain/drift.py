"""Drift detection engine — compare live image state against expected plan."""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

from stacksmith import __version__ as _builder_version

if TYPE_CHECKING:
    from stacksmith.domain.models import ArtifactRecord, Plan

log = logging.getLogger(__name__)


class DriftReason(str, Enum):
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"
    BASE_DIGEST_CHANGED = "base_digest_changed"
    TEMPLATE_HASH_CHANGED = "template_hash_changed"
    STACK_SCHEMA_CHANGED = "stack_schema_changed"
    PROFILE_SCHEMA_CHANGED = "profile_schema_changed"
    BLOCK_SCHEMA_CHANGED = "block_schema_changed"
    BUILDER_VERSION_CHANGED = "builder_version_changed"
    LABELS_MISSING = "labels_missing"


def detect_drift(
    labels: dict[str, str],
    catalog_record: ArtifactRecord | None,
    plan: Plan,
) -> list[DriftReason]:
    """Return a list of drift reasons by comparing image labels and catalog
    state against the current plan.  An empty list means no drift."""
    reasons: list[DriftReason] = []

    # If the image has no stacksmith labels at all, treat that as drift
    has_any_label = any(k.startswith("stacksmith.") for k in labels)
    if not has_any_label:
        reasons.append(DriftReason.LABELS_MISSING)
        return reasons

    live_fp = labels.get("stacksmith.fingerprint", "")
    if not live_fp or live_fp != plan.artifact.fingerprint:
        reasons.append(DriftReason.FINGERPRINT_MISMATCH)

    live_base = labels.get("stacksmith.base_digest", "")
    expected_base = plan.decision.base_digest or ""
    if live_base and expected_base and live_base != expected_base:
        reasons.append(DriftReason.BASE_DIGEST_CHANGED)

    live_tmpl = labels.get("stacksmith.template_hash", "")
    expected_tmpl = plan.artifact.labels.get("stacksmith.template_hash", "")
    if live_tmpl and expected_tmpl and live_tmpl != expected_tmpl:
        reasons.append(DriftReason.TEMPLATE_HASH_CHANGED)

    live_schema = labels.get("stacksmith.schema_version", "")
    expected_schema = plan.artifact.labels.get("stacksmith.schema_version", "")
    if live_schema and expected_schema and live_schema != expected_schema:
        reasons.append(DriftReason.STACK_SCHEMA_CHANGED)

    live_profile_schema = labels.get("stacksmith.profile_schema_version", "")
    expected_profile_schema = plan.artifact.labels.get("stacksmith.profile_schema_version", "")
    if live_profile_schema and expected_profile_schema and live_profile_schema != expected_profile_schema:
        reasons.append(DriftReason.PROFILE_SCHEMA_CHANGED)

    live_block_schema = labels.get("stacksmith.block_schema_version", "")
    expected_block_schema = plan.artifact.labels.get("stacksmith.block_schema_version", "")
    if live_block_schema and expected_block_schema and live_block_schema != expected_block_schema:
        reasons.append(DriftReason.BLOCK_SCHEMA_CHANGED)

    if catalog_record:
        try:
            expected_ver = int(expected_schema) if expected_schema else 1
        except (ValueError, TypeError):
            expected_ver = 1
        if catalog_record.stack_schema_version != expected_ver:
            if DriftReason.STACK_SCHEMA_CHANGED not in reasons:
                reasons.append(DriftReason.STACK_SCHEMA_CHANGED)
        try:
            expected_profile_ver = int(expected_profile_schema) if expected_profile_schema else 1
        except (ValueError, TypeError):
            expected_profile_ver = 1
        if getattr(catalog_record, "profile_schema_version", 1) != expected_profile_ver:
            if DriftReason.PROFILE_SCHEMA_CHANGED not in reasons:
                reasons.append(DriftReason.PROFILE_SCHEMA_CHANGED)
        try:
            expected_block_ver = int(expected_block_schema) if expected_block_schema else 1
        except (ValueError, TypeError):
            expected_block_ver = 1
        if getattr(catalog_record, "block_schema_version", 1) != expected_block_ver:
            if DriftReason.BLOCK_SCHEMA_CHANGED not in reasons:
                reasons.append(DriftReason.BLOCK_SCHEMA_CHANGED)

    live_bv = labels.get("stacksmith.builder_version", "")
    if live_bv and live_bv != _builder_version:
        reasons.append(DriftReason.BUILDER_VERSION_CHANGED)

    return reasons


def drift_summary(reasons: list[DriftReason]) -> str:
    """Return a human-readable comma-separated summary of drift reasons."""
    return ", ".join(r.value for r in reasons)


def is_stale(reasons: list[DriftReason]) -> bool:
    return bool(reasons)
