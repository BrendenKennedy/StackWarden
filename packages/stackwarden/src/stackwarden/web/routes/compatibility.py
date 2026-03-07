"""Compatibility preview endpoint for fail-fast UI/CLI feedback."""

from __future__ import annotations

from fastapi import APIRouter, Query

from stackwarden.config import compatibility_strict_default, load_layer, load_profile, load_stack
from stackwarden.resolvers.compatibility import evaluate_compatibility
from stackwarden.web.schemas import CompatibilityPreviewRequestDTO, CompatibilityPreviewResponseDTO

router = APIRouter(tags=["compatibility"])


@router.post("/compatibility/preview", response_model=CompatibilityPreviewResponseDTO)
def compatibility_preview(
    body: CompatibilityPreviewRequestDTO,
    strict: bool | None = Query(default=None),
):
    profile = load_profile(body.profile_id)
    stack = load_stack(body.stack_id)
    layers = [load_layer(layer_id) for layer_id in (stack.layers or [])]
    strict_mode = compatibility_strict_default() if strict is None else strict
    report = evaluate_compatibility(profile, stack, layers=layers, strict_mode=strict_mode)

    return CompatibilityPreviewResponseDTO.model_validate(report.model_dump(mode="json"))

