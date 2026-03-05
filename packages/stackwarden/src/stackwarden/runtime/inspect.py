"""Image inspection helpers — parse labels, extract StackWarden metadata."""

from __future__ import annotations

from typing import Any


LABEL_PREFIX = "stackwarden."

KNOWN_LABELS = (
    "stackwarden.profile",
    "stackwarden.stack",
    "stackwarden.fingerprint",
    "stackwarden.base_digest",
    "stackwarden.schema_version",
    "stackwarden.template_hash",
    "stackwarden.build_strategy",
    "stackwarden.builder_version",
    "stackwarden.created_at",
)


def extract_stackwarden_labels(labels: dict[str, str]) -> dict[str, str]:
    """Return only the stackwarden-prefixed labels."""
    return {k: v for k, v in labels.items() if k.startswith(LABEL_PREFIX)}


def fingerprint_matches(labels: dict[str, str], expected_fingerprint: str) -> bool:
    """Check whether the image's embedded fingerprint matches the expected one."""
    return labels.get("stackwarden.fingerprint", "") == expected_fingerprint


def format_image_info(attrs: dict[str, Any], catalog_entry: dict[str, Any] | None = None) -> dict:
    """Build a human-/machine-readable summary from Docker inspect attrs."""
    config = attrs.get("Config", {})
    labels = config.get("Labels", {}) or {}
    sw_labels = extract_stackwarden_labels(labels)

    info: dict[str, Any] = {
        "id": attrs.get("Id", "")[:19],
        "created": attrs.get("Created", ""),
        "size_mb": round((attrs.get("Size") or 0) / 1_048_576, 1),
        "repo_tags": attrs.get("RepoTags", []),
        "repo_digests": attrs.get("RepoDigests", []),
        "stackwarden": sw_labels,
    }

    if catalog_entry:
        info["catalog"] = catalog_entry

    return info
