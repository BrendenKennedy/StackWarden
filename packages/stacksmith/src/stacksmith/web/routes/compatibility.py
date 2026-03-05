"""Compatibility preview endpoint for fail-fast UI/CLI feedback."""

from __future__ import annotations

from fastapi import APIRouter, Query

from stacksmith.config import compatibility_strict_default, load_block, load_profile, load_stack
from stacksmith.resolvers.compatibility import evaluate_compatibility
from stacksmith.web.schemas import CompatibilityPreviewRequestDTO, CompatibilityPreviewResponseDTO

router = APIRouter(tags=["compatibility"])


@router.post("/compatibility/preview", response_model=CompatibilityPreviewResponseDTO)
def compatibility_preview(
    body: CompatibilityPreviewRequestDTO,
    strict: bool | None = Query(default=None),
):
    profile = load_profile(body.profile_id)
    stack = load_stack(body.stack_id)
    blocks = [load_block(block_id) for block_id in (stack.blocks or [])]
    strict_mode = compatibility_strict_default() if strict is None else strict
    report = evaluate_compatibility(profile, stack, blocks=blocks, strict_mode=strict_mode)

    return CompatibilityPreviewResponseDTO.model_validate(report.model_dump(mode="json"))

