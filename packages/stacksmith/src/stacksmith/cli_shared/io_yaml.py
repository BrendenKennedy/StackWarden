"""YAML load/edit/write helpers for CLI flows."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import yaml

from stacksmith.domain.errors import StacksmithError
from stacksmith.web.util.write_yaml import atomic_write_yaml


def atomic_write_spec(data: dict, target: Path) -> None:
    atomic_write_yaml(data, target)


def load_yaml_file(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise StacksmithError(f"YAML root must be a mapping: {path}")
    return data


def edit_yaml_via_editor(initial_data: dict) -> dict:
    editor = os.environ.get("EDITOR", "vi")
    fd, tmp = tempfile.mkstemp(suffix=".yaml", prefix="stacksmith-")
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(yaml.safe_dump(initial_data, sort_keys=False, default_flow_style=False))
        rc = subprocess.call([editor, tmp])
        if rc != 0:
            raise StacksmithError(f"Editor exited with status {rc}")
        return load_yaml_file(tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
