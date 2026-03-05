"""Atomic YAML writer with file + directory fsync."""

from __future__ import annotations

import os
from pathlib import Path

import yaml


def atomic_write_yaml(data: dict, target: Path) -> None:
    """Write *data* as YAML to *target* atomically.

    Sequence: write to tmp -> fsync file -> os.replace -> fsync directory.
    This ensures the rename is persisted even if the system crashes
    immediately after the call returns.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp")
    content = yaml.safe_dump(data, sort_keys=True, default_flow_style=False)

    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, content.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)

    os.replace(str(tmp), str(target))

    dirfd = os.open(str(target.parent), os.O_RDONLY)
    try:
        os.fsync(dirfd)
    finally:
        os.close(dirfd)


def serialize_for_yaml(model) -> dict:
    """Dump a Pydantic model to a dict suitable for YAML serialization.

    Uses ``mode="json"`` so enums become plain strings, and
    ``by_alias=True`` so that fields like ``copy_items`` serialise
    as their YAML alias (``copy``).
    """
    return model.model_dump(mode="json", by_alias=True)
