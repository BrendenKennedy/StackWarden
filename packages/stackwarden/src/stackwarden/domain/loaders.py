"""Bulk-loading helpers for profiles and stacks.

Kept separate from ``config.py`` (which handles ``AppConfig`` and
single-item loading) to avoid turning config into a junk drawer and
to reduce circular-import risk.
"""

from __future__ import annotations

from stackwarden.config import (
    list_layer_ids,
    list_profile_ids,
    list_stack_ids,
    load_layer,
    load_profile,
    load_stack,
)
from stackwarden.domain.models import LayerSpec, Profile, StackSpec


def load_all_profiles() -> list[Profile]:
    """Load every hardware profile found on disk."""
    return [load_profile(pid) for pid in list_profile_ids()]


def load_all_stacks() -> list[StackSpec]:
    """Load every stack spec found on disk."""
    return [load_stack(sid) for sid in list_stack_ids()]


def load_all_layers() -> list[LayerSpec]:
    """Load every layer spec found on disk."""
    return [load_layer(lid) for lid in list_layer_ids()]
