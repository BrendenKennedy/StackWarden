"""Cross-field validation beyond what Pydantic's type system enforces."""

from __future__ import annotations

from typing import TYPE_CHECKING

from stackwarden.domain.errors import ValidationError

if TYPE_CHECKING:
    from stackwarden.domain.models import Profile, StackSpec


def validate_profile(profile: Profile) -> None:
    is_v2 = profile.schema_version >= 2
    is_v3 = profile.schema_version >= 3
    if not is_v2 and not profile.base_candidates:
        raise ValidationError("base_candidates", "Profile must have at least one base candidate")
    if "cuda" in profile.derived_capabilities and profile.cuda is not None:
        if profile.cuda.major <= 0:
            raise ValidationError("cuda.major", "CUDA major version must be positive")
        if profile.cuda.minor < 0:
            raise ValidationError("cuda.minor", "CUDA minor version must be non-negative")
    if is_v3 and "cuda" in profile.derived_capabilities and profile.cuda is None:
        raise ValidationError(
            "derived_capabilities",
            "derived_capabilities includes cuda but cuda details are missing",
        )
    for candidate in profile.base_candidates:
        if not candidate.tags:
            raise ValidationError(
                f"base_candidates[{candidate.name}].tags",
                "Each base candidate must have at least one tag",
            )


def validate_stack(stack: StackSpec) -> None:
    is_v2_composition = stack.schema_version >= 2 and bool(stack.layers)
    is_v3 = stack.schema_version >= 3
    if not is_v2_composition and not stack.components.base_role:
        raise ValidationError("components.base_role", "Stack must declare a base_role")
    if not is_v2_composition and not stack.entrypoint.cmd:
        raise ValidationError("entrypoint.cmd", "Stack must have a non-empty entrypoint cmd")
    if is_v3 and stack.derived_capabilities and not stack.requirements.needs:
        raise ValidationError(
            "requirements.needs",
            "schema v3 requires requirements.needs when derived_capabilities are present",
        )
