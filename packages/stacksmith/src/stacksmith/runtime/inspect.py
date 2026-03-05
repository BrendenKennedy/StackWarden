"""Image inspection helpers — parse labels, extract stacksmith metadata."""

from __future__ import annotations

from typing import Any


LABEL_PREFIX = "stacksmith."

KNOWN_LABELS = (
    "stacksmith.profile",
    "stacksmith.stack",
    "stacksmith.fingerprint",
    "stacksmith.base_digest",
    "stacksmith.schema_version",
    "stacksmith.template_hash",
    "stacksmith.build_strategy",
    "stacksmith.builder_version",
    "stacksmith.created_at",
)


def extract_stacksmith_labels(labels: dict[str, str]) -> dict[str, str]:
    """Return only the stacksmith-prefixed labels."""
    return {k: v for k, v in labels.items() if k.startswith(LABEL_PREFIX)}


def fingerprint_matches(labels: dict[str, str], expected_fingerprint: str) -> bool:
    """Check whether the image's embedded fingerprint matches the expected one."""
    return labels.get("stacksmith.fingerprint", "") == expected_fingerprint


def format_image_info(attrs: dict[str, Any], catalog_entry: dict[str, Any] | None = None) -> dict:
    """Build a human-/machine-readable summary from Docker inspect attrs."""
    config = attrs.get("Config", {})
    labels = config.get("Labels", {}) or {}
    sm_labels = extract_stacksmith_labels(labels)

    info: dict[str, Any] = {
        "id": attrs.get("Id", "")[:19],
        "created": attrs.get("Created", ""),
        "size_mb": round((attrs.get("Size") or 0) / 1_048_576, 1),
        "repo_tags": attrs.get("RepoTags", []),
        "repo_digests": attrs.get("RepoDigests", []),
        "stacksmith": sm_labels,
    }

    if catalog_entry:
        info["catalog"] = catalog_entry

    return info
