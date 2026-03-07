"""High-risk command registration helpers."""

from __future__ import annotations


def command_map() -> dict[str, tuple[str, ...]]:
    return {
        "planning": ("plan", "check_cmd"),
        "build": ("ensure", "wizard"),
        "operations": ("status", "prune_cmd", "doctor", "init"),
        "artifacts": ("verify", "inspect_cmd", "inspect_layer_cmd", "compose_cmd", "manifest_cmd", "repro_cmd", "sbom_cmd"),
        "catalog": ("catalog_search", "catalog_build", "catalog_show", "catalog_stale", "catalog_prune", "catalog_disk_usage"),
        "migration": ("migrate_v1_to_v2",),
    }
