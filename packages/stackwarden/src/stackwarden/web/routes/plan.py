"""Plan preview endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from stackwarden.config import (
    compatibility_strict_default,
    load_layer,
    load_profile,
    load_stack,
    strict_host_optimization_default,
)
from stackwarden.domain.variants import validate_variant_flags
from stackwarden.resolvers.resolver import resolve
from stackwarden.web.schemas import PlanRequestDTO, PlanResponseDTO

router = APIRouter(tags=["plan"])


@router.post("/plan", response_model=PlanResponseDTO)
def preview_plan(body: PlanRequestDTO):
    profile = load_profile(body.profile_id)
    stack = load_stack(body.stack_id)
    layers = [load_layer(layer_id) for layer_id in (stack.layers or [])]

    if body.variants:
        validate_variant_flags(stack, body.variants)

    explain = body.flags.get("explain", False)

    plan = resolve(
        profile,
        stack,
        layers=layers,
        variants=body.variants,
        explain=explain,
        strict_mode=compatibility_strict_default(),
        strict_host_optimization=strict_host_optimization_default(),
    )

    return PlanResponseDTO.from_domain(plan)
