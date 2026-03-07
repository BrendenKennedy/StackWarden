"""Drift detection engine — compare live image state against expected plan."""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

from stackwarden import __version__ as _builder_version

if TYPE_CHECKING:
    from stackwarden.domain.models import ArtifactRecord, Plan

log = logging.getLogger(__name__)


class DriftReason(str, Enum):
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"
    BASE_DIGEST_CHANGED = "base_digest_changed"
    TEMPLATE_HASH_CHANGED = "template_hash_changed"
    STACK_SCHEMA_CHANGED = "stack_schema_changed"
    PROFILE_SCHEMA_CHANGED = "profile_schema_changed"
    # Legacy reason value retained for compatibility while layer-first naming
    # becomes canonical in internal code paths.
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

    # If the image has no stackwarden labels at all, treat that as drift
    has_any_label = any(k.startswith("stackwarden.") for k in labels)
    if not has_any_label:
        reasons.append(DriftReason.LABELS_MISSING)
        return reasons

    live_fp = labels.get("stackwarden.fingerprint", "")
    if not live_fp or live_fp != plan.artifact.fingerprint:
        reasons.append(DriftReason.FINGERPRINT_MISMATCH)

    live_base = labels.get("stackwarden.base_digest", "")
    expected_base = plan.decision.base_digest or ""
    if live_base and expected_base and live_base != expected_base:
        reasons.append(DriftReason.BASE_DIGEST_CHANGED)

    live_tmpl = labels.get("stackwarden.template_hash", "")
    expected_tmpl = plan.artifact.labels.get("stackwarden.template_hash", "")
    if live_tmpl and expected_tmpl and live_tmpl != expected_tmpl:
        reasons.append(DriftReason.TEMPLATE_HASH_CHANGED)

    live_schema = labels.get("stackwarden.schema_version", "")
    expected_schema = plan.artifact.labels.get("stackwarden.schema_version", "")
    if live_schema and expected_schema and live_schema != expected_schema:
        reasons.append(DriftReason.STACK_SCHEMA_CHANGED)

    live_profile_schema = labels.get("stackwarden.profile_schema_version", "")
    expected_profile_schema = plan.artifact.labels.get("stackwarden.profile_schema_version", "")
    if live_profile_schema and expected_profile_schema and live_profile_schema != expected_profile_schema:
        reasons.append(DriftReason.PROFILE_SCHEMA_CHANGED)

    live_layer_schema = labels.get(
        "stackwarden.layer_schema_version",
        labels.get("stackwarden.block_schema_version", ""),
    )
    expected_layer_schema = plan.artifact.labels.get(
        "stackwarden.layer_schema_version",
        plan.artifact.labels.get("stackwarden.block_schema_version", ""),
    )
    if live_layer_schema and expected_layer_schema and live_layer_schema != expected_layer_schema:
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
            expected_layer_ver = int(expected_layer_schema) if expected_layer_schema else 1
        except (ValueError, TypeError):
            expected_layer_ver = 1
        catalog_layer_schema = getattr(
            catalog_record,
            "layer_schema_version",
            getattr(catalog_record, "block_schema_version", 1),
        )
        if catalog_layer_schema != expected_layer_ver:
            if DriftReason.BLOCK_SCHEMA_CHANGED not in reasons:
                reasons.append(DriftReason.BLOCK_SCHEMA_CHANGED)

    live_bv = labels.get("stackwarden.builder_version", "")
    if live_bv and live_bv != _builder_version:
        reasons.append(DriftReason.BUILDER_VERSION_CHANGED)

    return reasons


def drift_summary(reasons: list[DriftReason]) -> str:
    """Return a human-readable comma-separated summary of drift reasons."""
    return ", ".join(r.value for r in reasons)


def is_stale(reasons: list[DriftReason]) -> bool:
    return bool(reasons)
