"""Plan preview endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from stacksmith.config import compatibility_strict_default, load_block, load_profile, load_stack
from stacksmith.domain.variants import validate_variant_flags
from stacksmith.resolvers.resolver import resolve
from stacksmith.web.schemas import PlanRequestDTO, PlanResponseDTO

router = APIRouter(tags=["plan"])


@router.post("/plan", response_model=PlanResponseDTO)
def preview_plan(body: PlanRequestDTO):
    profile = load_profile(body.profile_id)
    stack = load_stack(body.stack_id)
    blocks = [load_block(block_id) for block_id in (stack.blocks or [])]

    if body.variants:
        validate_variant_flags(stack, body.variants)

    explain = body.flags.get("explain", False)

    plan = resolve(
        profile,
        stack,
        blocks=blocks,
        variants=body.variants,
        explain=explain,
        strict_mode=compatibility_strict_default(),
    )

    return PlanResponseDTO.from_domain(plan)
