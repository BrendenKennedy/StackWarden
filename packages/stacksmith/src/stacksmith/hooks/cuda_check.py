"""CUDA visibility hook — verify GPU access inside the container.

Only runs when profile capability state/facts indicate CUDA is expected.
Skips silently (success + warning) otherwise.
"""

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING

from stacksmith.hooks.protocol import HookResult

if TYPE_CHECKING:
    from stacksmith.domain.models import Profile, StackSpec

log = logging.getLogger(__name__)


class CudaVisibilityHook:
    name = "cuda_visibility"

    def run(self, tag: str, profile: Profile, stack: StackSpec) -> HookResult:
        expects_cuda = (
            "cuda" in (profile.derived_capabilities or [])
            or (profile.cuda is not None and profile.cuda.major > 0)
        )
        if not expects_cuda:
            return HookResult(
                success=True,
                warnings=["Skipped: profile does not indicate CUDA capability"],
            )

        try:
            result = subprocess.run(
                ["docker", "run", "--rm", "--gpus", "all", "--entrypoint", "", tag,
                 "python", "-c",
                 "import torch; assert torch.cuda.is_available(), 'CUDA not available'"],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                return HookResult(success=True)
            return HookResult(
                success=False,
                logs=f"CUDA check failed: {result.stderr.strip()[:300]}",
            )
        except subprocess.TimeoutExpired:
            return HookResult(success=False, logs="CUDA check timed out")
        except FileNotFoundError:
            return HookResult(
                success=True,
                warnings=["docker not available for CUDA check — skipped"],
            )
