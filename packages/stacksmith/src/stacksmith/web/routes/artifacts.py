"""Artifact / catalog endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from stacksmith.catalog.store import CatalogStore
from stacksmith.domain.snapshots import artifact_dir
from stacksmith.web.deps import get_catalog
from stacksmith.web.schemas import ArtifactDetailDTO, ArtifactSummaryDTO

router = APIRouter(tags=["artifacts"])

_ALLOWED_FILES = frozenset({"manifest", "profile", "stack", "plan", "sbom", "verify"})


@router.get("/artifacts", response_model=list[ArtifactSummaryDTO])
async def list_artifacts(
    profile_id: str | None = None,
    stack_id: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    catalog: CatalogStore = Depends(get_catalog),
):
    records = catalog.search_artifacts(
        profile_id=profile_id,
        stack_id=stack_id,
        status=status,
        q=q,
        limit=limit,
        offset=offset,
    )
    return [ArtifactSummaryDTO.from_domain(r) for r in records]


@router.get("/artifacts/{artifact_id}", response_model=ArtifactDetailDTO)
async def get_artifact(
    artifact_id: str,
    catalog: CatalogStore = Depends(get_catalog),
):
    record = _find_artifact(artifact_id, catalog)
    return ArtifactDetailDTO.from_domain(record)


@router.get("/artifacts/{artifact_id}/files/{name}")
async def get_artifact_file(
    artifact_id: str,
    name: str,
    catalog: CatalogStore = Depends(get_catalog),
):
    if name not in _ALLOWED_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file name: {name}. Allowed: {', '.join(sorted(_ALLOWED_FILES))}",
        )
    record = _find_artifact(artifact_id, catalog)
    art_dir = artifact_dir(record.fingerprint)
    file_path = art_dir / f"{name}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {name}.json")
    if not file_path.resolve().is_relative_to(art_dir.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")
    data = json.loads(file_path.read_text())
    return JSONResponse(content=data)


@router.post("/artifacts/{artifact_id}/mark-stale")
async def mark_artifact_stale(
    artifact_id: str,
    catalog: CatalogStore = Depends(get_catalog),
):
    record = _find_artifact(artifact_id, catalog)
    count = catalog.mark_stale(record.profile_id, record.stack_id, reason="manual")
    return {"marked": count}


@router.delete("/artifacts/{artifact_id}")
async def delete_artifact(
    artifact_id: str,
    catalog: CatalogStore = Depends(get_catalog),
):
    """Remove an artifact from the catalog (prune). Works for failed, stale, or built artifacts."""
    record = _find_artifact(artifact_id, catalog)
    catalog.prune_artifact(record.id)
    return {"deleted": True, "id": record.id}


def _find_artifact(artifact_id: str, catalog: CatalogStore):
    record = catalog.get_artifact_by_tag(artifact_id)
    if not record:
        record = catalog.get_artifact_by_fingerprint(artifact_id)
    if not record:
        record = catalog.get_artifact_by_id(artifact_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Artifact not found: {artifact_id}")
    return record
