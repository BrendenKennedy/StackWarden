"""Build-level file locking to prevent concurrent builds on the same target.

Lock granularity is (profile_id, stack_id, variant_hash).  The lock is
acquired after plan generation but before the image existence check to
prevent TOCTOU races.
"""

from __future__ import annotations

import hashlib
import logging
import re
from contextlib import contextmanager
from typing import Generator

import time

from filelock import FileLock, Timeout  # noqa: F401 — Timeout re-exported for callers

from stacksmith.paths import get_locks_root

log = logging.getLogger(__name__)

_UNSAFE_CHARS = re.compile(r"[^a-zA-Z0-9._-]")


def compute_variant_hash(variants: dict[str, str] | None) -> str:
    """Deterministic short hash of normalized variant overrides."""
    if not variants:
        return ""
    from stacksmith.domain.hashing import canonical_json

    normalized = {k: str(v) for k, v in sorted(variants.items())}
    return hashlib.sha256(canonical_json(normalized).encode()).hexdigest()[:12]


def _lock_key(profile_id: str, stack_id: str, variant_hash: str = "") -> str:
    return f"{profile_id}:{stack_id}:{variant_hash}"


def _sanitize_filename(key: str) -> str:
    return _UNSAFE_CHARS.sub("_", key)


@contextmanager
def acquire_lock(
    profile_id: str,
    stack_id: str,
    variant_hash: str = "",
    timeout: float = 300,
) -> Generator[None, None, None]:
    """Context manager that holds a file lock for the given build target.

    Raises ``filelock.Timeout`` if the lock cannot be acquired within
    *timeout* seconds.
    """
    locks_dir = get_locks_root()
    locks_dir.mkdir(parents=True, exist_ok=True)
    key = _lock_key(profile_id, stack_id, variant_hash)
    safe = _sanitize_filename(key)
    lock_path = locks_dir / f"{safe}.lock"
    lock = FileLock(lock_path, timeout=timeout)
    log.debug("Acquiring lock %s (timeout=%ss)", lock_path, timeout)
    with lock:
        yield


def cleanup_stale_locks(max_age_seconds: int = 86400) -> int:
    """Remove lock files older than *max_age_seconds*. Returns count removed."""
    locks_dir = get_locks_root()
    if not locks_dir.is_dir():
        return 0
    now = time.time()
    removed = 0
    for lock_file in locks_dir.glob("*.lock"):
        try:
            if now - lock_file.stat().st_mtime > max_age_seconds:
                lock_file.unlink(missing_ok=True)
                removed += 1
        except OSError:
            pass
    if removed:
        log.debug("Cleaned up %d stale lock file(s)", removed)
    return removed
