"""Bulk-loading helpers for profiles and stacks.

Kept separate from ``config.py`` (which handles ``AppConfig`` and
single-item loading) to avoid turning config into a junk drawer and
to reduce circular-import risk.
"""

from __future__ import annotations

from stacksmith.config import (
    list_block_ids,
    list_profile_ids,
    list_stack_ids,
    load_block,
    load_profile,
    load_stack,
)
from stacksmith.domain.models import BlockSpec, Profile, StackSpec


def load_all_profiles() -> list[Profile]:
    """Load every hardware profile found on disk."""
    return [load_profile(pid) for pid in list_profile_ids()]


def load_all_stacks() -> list[StackSpec]:
    """Load every stack spec found on disk."""
    return [load_stack(sid) for sid in list_stack_ids()]


def load_all_blocks() -> list[BlockSpec]:
    """Load every block spec found on disk."""
    return [load_block(bid) for bid in list_block_ids()]
