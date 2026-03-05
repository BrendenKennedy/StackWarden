"""Post-build validation hooks.

Hooks are **read-only** validation containers.  They run via
``docker run --rm`` and must never modify the built image.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stackwarden.hooks.protocol import PostBuildHook

HOOK_REGISTRY: list[PostBuildHook] = []
_lock = threading.Lock()
_loaded = False


def _load_builtin_hooks() -> None:
    global _loaded
    if _loaded:
        return
    with _lock:
        if _loaded:
            return
        from stackwarden.hooks.import_smoke import ImportSmokeHook
        from stackwarden.hooks.cuda_check import CudaVisibilityHook

        HOOK_REGISTRY.clear()
        HOOK_REGISTRY.extend([ImportSmokeHook(), CudaVisibilityHook()])
        _loaded = True


def get_hooks() -> list[PostBuildHook]:
    _load_builtin_hooks()
    return HOOK_REGISTRY
