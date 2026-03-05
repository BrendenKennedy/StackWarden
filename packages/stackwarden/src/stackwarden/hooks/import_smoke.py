"""Import smoke-test hook — verify primary packages are importable."""

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING

from stackwarden.hooks.protocol import HookResult

if TYPE_CHECKING:
    from stackwarden.domain.models import Profile, StackSpec

log = logging.getLogger(__name__)

_TASK_IMPORTS: dict[str, list[str]] = {
    "llm": ["torch", "transformers"],
    "diffusion": ["torch", "diffusers"],
    "embedding": ["torch"],
    "vision": ["torch", "torchvision"],
    "asr": ["torch"],
    "tts": ["torch"],
}

_SERVE_IMPORTS: dict[str, list[str]] = {
    "vllm": ["vllm"],
}


class ImportSmokeHook:
    name = "import_smoke"

    def run(self, tag: str, profile: Profile, stack: StackSpec) -> HookResult:
        packages = set()
        packages.update(_TASK_IMPORTS.get(stack.task.value, []))
        packages.update(_SERVE_IMPORTS.get(stack.serve.value, []))

        if not packages:
            return HookResult(success=True, warnings=["No import targets for this stack"])

        sorted_packages = sorted(packages)
        import_script = "; ".join(f"import {pkg}" for pkg in sorted_packages)

        try:
            result = subprocess.run(
                ["docker", "run", "--rm", "--entrypoint", "", tag,
                 "python", "-c", import_script],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                return HookResult(
                    success=False,
                    logs=f"Import check failed for [{', '.join(sorted_packages)}]:\n"
                         f"{result.stderr.strip()[:500]}",
                )
        except subprocess.TimeoutExpired:
            return HookResult(
                success=False,
                logs=f"Import check timed out for: {', '.join(sorted_packages)}",
            )
        except FileNotFoundError as exc:
            return HookResult(
                success=True,
                warnings=[f"docker not available for import check — skipped: {exc}"],
            )

        return HookResult(success=True)
