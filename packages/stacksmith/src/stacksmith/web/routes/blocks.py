"""Block endpoints."""

from __future__ import annotations
import logging

from fastapi import APIRouter, HTTPException, Query, Response

from stacksmith.application.create_flows import (
    AppNotFoundError,
    AppValidationError,
    update_block as app_update_block,
)
from stacksmith.config import get_block_origin, get_blocks_dir, list_block_ids, load_block
from stacksmith.domain.errors import BlockNotFoundError
from stacksmith.web.schemas import BlockCreateRequest, BlockCreateResponse, BlockDetailDTO, BlockSummaryDTO
from stacksmith.web.util.versioning import apply_version_headers, resolve_schema_version
from stacksmith.web.util.write_yaml import serialize_for_yaml

router = APIRouter(tags=["blocks"])
log = logging.getLogger(__name__)


def _validation_422(errors: list[dict[str, str]]):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=422, content={"detail": errors})


@router.get("/blocks", response_model=list[BlockSummaryDTO])
async def list_blocks(response: Response, schema: str | None = Query(default=None)):
    apply_version_headers(response, requested=resolve_schema_version(schema))
    blocks = []
    skipped = 0
    for bid in list_block_ids():
        try:
            blocks.append(load_block(bid))
        except Exception as exc:  # noqa: BLE001 - keep listing resilient
            skipped += 1
            log.warning("Skipping invalid block during list: id=%s error=%s", bid, exc)
    if skipped:
        response.headers["X-Stacksmith-Blocks-Skipped"] = str(skipped)
    return [BlockSummaryDTO.from_domain(b, origin=get_block_origin(b.id)) for b in blocks]


@router.get("/blocks/{block_id}", response_model=BlockDetailDTO)
async def get_block(block_id: str, response: Response, schema: str | None = Query(default=None)):
    apply_version_headers(response, requested=resolve_schema_version(schema))
    try:
        block = load_block(block_id)
    except BlockNotFoundError:
        raise HTTPException(status_code=404, detail=f"Block not found: {block_id}")
    return BlockDetailDTO.from_domain(block, origin=get_block_origin(block.id))


@router.get("/blocks/{block_id}/spec")
async def get_block_spec(block_id: str):
    try:
        block = load_block(block_id)
    except BlockNotFoundError:
        raise HTTPException(status_code=404, detail=f"Block not found: {block_id}")
    return serialize_for_yaml(block)


@router.put("/blocks/{block_id}", response_model=BlockCreateResponse)
async def update_block(block_id: str, req: BlockCreateRequest):
    try:
        target = app_update_block(block_id, req)
    except AppValidationError as exc:
        return _validation_422(exc.errors)
    except AppNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    return BlockCreateResponse(id=block_id, display_name=req.display_name, path=str(target))


@router.delete("/blocks/{block_id}")
async def delete_block(block_id: str):
    blocks_dir = get_blocks_dir()
    target = (blocks_dir / f"{block_id}.yaml").resolve()
    if not target.is_relative_to(blocks_dir.resolve()):
        raise HTTPException(status_code=400, detail=f"Invalid block id: {block_id}")
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Block not found: {block_id}")
    target.unlink()
    return {"deleted": True, "id": block_id}

