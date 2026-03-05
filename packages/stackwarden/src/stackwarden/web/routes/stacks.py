"""Stack endpoints."""

from __future__ import annotations
import logging

from fastapi import APIRouter, HTTPException, Query, Response

from stackwarden.application.create_flows import (
    AppNotFoundError,
    AppValidationError,
    update_stack as app_update_stack,
)
from stackwarden.config import get_stack_origin, get_stacks_dir, list_stack_ids, load_stack, load_stack_spec_raw
from stackwarden.domain.errors import StackNotFoundError
from stackwarden.web.schemas import (
    StackCreateRequest,
    StackCreateResponse,
    StackDetailDTO,
    StackSummaryDTO,
)
from stackwarden.web.util.versioning import apply_version_headers, resolve_schema_version

router = APIRouter(tags=["stacks"])
log = logging.getLogger(__name__)


def _validation_422(errors: list[dict[str, str]]):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=422, content={"detail": errors})


@router.get("/stacks", response_model=list[StackSummaryDTO])
async def list_stacks(response: Response, schema: str | None = Query(default=None)):
    apply_version_headers(response, requested=resolve_schema_version(schema))
    stacks = []
    skipped = 0
    for sid in list_stack_ids():
        try:
            stacks.append(load_stack(sid))
        except Exception as exc:  # noqa: BLE001 - keep listing resilient
            skipped += 1
            log.warning("Skipping invalid stack during list: id=%s error=%s", sid, exc)
    if skipped:
        response.headers["X-StackWarden-Stacks-Skipped"] = str(skipped)
    return [StackSummaryDTO.from_domain(s, origin=get_stack_origin(s.id)) for s in stacks]


@router.get("/stacks/{stack_id}", response_model=StackDetailDTO)
async def get_stack(stack_id: str, response: Response, schema: str | None = Query(default=None)):
    apply_version_headers(response, requested=resolve_schema_version(schema))
    try:
        s = load_stack(stack_id)
    except StackNotFoundError:
        raise HTTPException(status_code=404, detail=f"Stack not found: {stack_id}")
    return StackDetailDTO.from_domain(s, origin=get_stack_origin(s.id))


@router.get("/stacks/{stack_id}/spec")
async def get_stack_spec(stack_id: str):
    try:
        s = load_stack_spec_raw(stack_id)
    except StackNotFoundError:
        raise HTTPException(status_code=404, detail=f"Stack not found: {stack_id}")
    return s


@router.put("/stacks/{stack_id}", response_model=StackCreateResponse)
async def update_stack(stack_id: str, req: StackCreateRequest):
    try:
        target = app_update_stack(stack_id, req)
    except AppValidationError as exc:
        return _validation_422(exc.errors)
    except AppNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    return StackCreateResponse(id=stack_id, display_name=req.display_name, path=str(target))


@router.delete("/stacks/{stack_id}")
async def delete_stack(stack_id: str):
    try:
        stacks_dir = get_stacks_dir()
        target = (stacks_dir / f"{stack_id}.yaml").resolve()
        if not target.is_relative_to(stacks_dir.resolve()):
            raise HTTPException(status_code=400, detail=f"Invalid stack id: {stack_id}")
        if not target.exists():
            raise HTTPException(status_code=404, detail=f"Stack not found: {stack_id}")
        target.unlink()
        return {"deleted": True, "id": stack_id}
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to delete stack: %s", stack_id)
        raise
