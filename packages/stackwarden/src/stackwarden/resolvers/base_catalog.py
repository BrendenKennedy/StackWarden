"""Runtime/base candidate catalog and deterministic selection helpers."""

from __future__ import annotations

from dataclasses import dataclass

from stackwarden.domain.models import Profile, StackSpec


@dataclass(frozen=True)
class RuntimeBaseCandidate:
    name: str
    tags: list[str]
    score_bias: int = 0
    source: str = "profile"


def candidates_for(profile: Profile, stack: StackSpec) -> list[RuntimeBaseCandidate]:
    """Return candidate list from policy override, profile, then sane defaults."""
    overrides = stack.policy_overrides or {}
    base_image = overrides.get("base_image")
    base_tag = overrides.get("base_tag")
    if isinstance(base_image, str) and base_image.strip():
        return [
            RuntimeBaseCandidate(
                name=base_image.strip(),
                tags=[str(base_tag).strip()] if base_tag else ["latest"],
                score_bias=1000,
                source="policy_override",
            )
        ]

    if profile.base_candidates:
        return [
            RuntimeBaseCandidate(
                name=c.name,
                tags=c.tags,
                score_bias=c.score_bias,
                source="profile",
            )
            for c in profile.base_candidates
        ]

    # Blocks-first fallback: rely on derived capabilities + concrete runtime facts.
    effective_caps = set(profile.derived_capabilities or [])
    if profile.cuda is not None and profile.cuda.major > 0:
        effective_caps.add("cuda")
    if profile.container_runtime.value.lower() == "nvidia":
        effective_caps.add("cuda")

    if "cuda" in effective_caps:
        return [RuntimeBaseCandidate(name="nvidia/cuda", tags=["12.4.1-runtime-ubuntu22.04"], source="default")]
    return [RuntimeBaseCandidate(name="python", tags=["3.10-slim"], source="default")]

