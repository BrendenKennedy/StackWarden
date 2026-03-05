"""Centralized filesystem paths for StackWarden.

Single source of truth for all data, config, and artifact locations.
No other module should hardcode ``~/.local/share/stackwarden/...`` or
``~/.config/stackwarden/...``.

Honors XDG Base Directory env vars (``XDG_DATA_HOME``, ``XDG_CONFIG_HOME``)
when available.
"""

from __future__ import annotations

import os
from pathlib import Path


def _data_root() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "stackwarden"
    return Path.home() / ".local" / "share" / "stackwarden"


def _config_root() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "stackwarden"
    return Path.home() / ".config" / "stackwarden"


def get_data_root() -> Path:
    return _data_root()


def get_config_root() -> Path:
    return _config_root()


def get_artifacts_root() -> Path:
    return _data_root() / "artifacts"


def get_locks_root() -> Path:
    return _data_root() / "locks"


def get_logs_root() -> Path:
    return _data_root() / "logs"


def get_catalog_path() -> Path:
    return _data_root() / "catalog.db"


def get_config_path() -> Path:
    return _config_root() / "config.yaml"
