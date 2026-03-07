"""Layer endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Response

from stackwarden.application.create_flows import (
    AppNotFoundError,
    AppValidationError,
    update_layer as app_update_layer,
)
from stackwarden.application.layer_option_classifier import classify_layer_options
from stackwarden.config import get_layer_origin, get_layers_dir, list_layer_ids, load_layer
from stackwarden.domain.errors import LayerNotFoundError, ProfileNotFoundError
from stackwarden.web.schemas import (
    LayerCreateRequest,
    LayerCreateResponse,
    LayerDetailDTO,
    LayerOptionDTO,
    LayerOptionGroupDTO,
    LayerOptionsClassifyRequestDTO,
    LayerOptionsClassifyResponseDTO,
    LayerSummaryDTO,
)
from stackwarden.web.util.responses import validation_422
from stackwarden.web.util.versioning import apply_version_headers, resolve_schema_version
from stackwarden.web.util.write_yaml import serialize_for_yaml

router = APIRouter(tags=["layers"])
log = logging.getLogger(__name__)


@router.get("/layers", response_model=list[LayerSummaryDTO])
async def list_layers(response: Response, schema: str | None = Query(default=None)):
    apply_version_headers(response, requested=resolve_schema_version(schema))
    layers = []
    skipped = 0
    for layer_id in list_layer_ids():
        try:
            layers.append(load_layer(layer_id))
        except Exception as exc:  # noqa: BLE001 - keep listing resilient
            skipped += 1
            log.warning("Skipping invalid layer during list: id=%s error=%s", layer_id, exc)
    if skipped:
        response.headers["X-StackWarden-Layers-Skipped"] = str(skipped)
    return [LayerSummaryDTO.from_domain(layer, origin=get_layer_origin(layer.id)) for layer in layers]


@router.get("/layers/{layer_id}", response_model=LayerDetailDTO)
async def get_layer(layer_id: str, response: Response, schema: str | None = Query(default=None)):
    apply_version_headers(response, requested=resolve_schema_version(schema))
    try:
        layer = load_layer(layer_id)
    except LayerNotFoundError:
        raise HTTPException(status_code=404, detail=f"Layer not found: {layer_id}")
    return LayerDetailDTO.from_domain(layer, origin=get_layer_origin(layer.id))


@router.get("/layers/{layer_id}/spec")
async def get_layer_spec(layer_id: str):
    try:
        layer = load_layer(layer_id)
    except LayerNotFoundError:
        raise HTTPException(status_code=404, detail=f"Layer not found: {layer_id}")
    return serialize_for_yaml(layer)


@router.post("/layers/options/classify", response_model=LayerOptionsClassifyResponseDTO)
async def classify_layer_options_for_wizard(req: LayerOptionsClassifyRequestDTO):
    try:
        groups = classify_layer_options(
            selected_layers=req.selected_layers,
            inference_type=req.inference_type,
            inference_profile=req.inference_profile,
            target_profile_id=req.target_profile_id,
        )
    except ProfileNotFoundError:
        raise HTTPException(status_code=422, detail=f"Profile not found: {req.target_profile_id}")
    payload = [
        LayerOptionGroupDTO(
            stack_layer=group.stack_layer,
            options=[
                LayerOptionDTO(
                    id=item.id,
                    display_name=item.display_name,
                    stack_layer=item.stack_layer,
                    tags=item.tags,
                    tier=item.tier,
                    score=item.score,
                    reasons=item.reasons,
                    selected=item.selected,
                )
                for item in group.options
            ],
        )
        for group in groups
    ]
    return LayerOptionsClassifyResponseDTO(groups=payload)


@router.put("/layers/{layer_id}", response_model=LayerCreateResponse)
async def update_layer(layer_id: str, req: LayerCreateRequest):
    try:
        target = app_update_layer(layer_id, req)
    except AppValidationError as exc:
        return validation_422(exc.errors)
    except AppNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    return LayerCreateResponse(id=layer_id, display_name=req.display_name, path=str(target))


@router.delete("/layers/{layer_id}")
async def delete_layer(layer_id: str):
    layers_dir = get_layers_dir()
    target = (layers_dir / f"{layer_id}.yaml").resolve()
    if not target.is_relative_to(layers_dir.resolve()):
        raise HTTPException(status_code=400, detail=f"Invalid layer id: {layer_id}")
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Layer not found: {layer_id}")
    target.unlink()
    return {"deleted": True, "id": layer_id}
