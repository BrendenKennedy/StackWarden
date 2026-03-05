"""Application-facing YAML serialization adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from stackwarden.web.util.write_yaml import atomic_write_yaml, serialize_for_yaml

__all__ = ["atomic_write_yaml", "serialize_for_yaml"]


def write_payload(payload: dict[str, Any], target: Path) -> None:
    """Small indirection point for application-layer writes."""
    atomic_write_yaml(payload, target)
