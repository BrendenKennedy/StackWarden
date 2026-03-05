"""Hook protocol and result types.

All hooks MUST be read-only validators.  They receive an image tag (a
read-only reference) and run ``docker run --rm`` to inspect the image.
Hooks must never modify the built image — doing so would break
fingerprint integrity.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from stackwarden.domain.models import Profile, StackSpec


class HookResult(BaseModel):
    success: bool
    logs: str = ""
    warnings: list[str] = Field(default_factory=list)


@runtime_checkable
class PostBuildHook(Protocol):
    name: str

    def run(self, tag: str, profile: Profile, stack: StackSpec) -> HookResult: ...
