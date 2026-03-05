"""Consolidated catalog lifecycle endpoint."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from stackwarden.catalog.store import CatalogStore
from stackwarden.web.deps import get_catalog, get_job_manager
from stackwarden.web.jobs.manager import JobManager
from stackwarden.web.schemas import CatalogItemDTO

router = APIRouter(tags=["catalog"])


def _norm_artifact_status(status: str) -> str:
    mapping = {
        "planned": "queued",
        "building": "running",
        "built": "built",
        "failed": "failed",
        "stale": "stale",
    }
    return mapping.get(status, status)


def _norm_job_status(status: str, has_artifact: bool) -> str:
    if status == "succeeded":
        # Keep transitional running state until artifact row exists.
        return "built" if has_artifact else "running"
    return status


def _ts(item: CatalogItemDTO) -> float:
    try:
        return datetime.fromisoformat(item.created_at).timestamp()
    except Exception:
        return 0.0


@router.get("/catalog/items", response_model=list[CatalogItemDTO])
async def list_catalog_items(
    status: str | None = None,
    profile_id: str | None = None,
    stack_id: str | None = None,
    q: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    catalog: CatalogStore = Depends(get_catalog),
    jobs: JobManager = Depends(get_job_manager),
):
    try:
        artifacts = catalog.search_artifacts(
            profile_id=profile_id,
            stack_id=stack_id,
            status=None,
            q=q,
            limit=None,
            offset=None,
        )
        job_rows = jobs.list_jobs(limit=None)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface internal faults as 5xx
        raise HTTPException(status_code=500, detail=f"Catalog list failed: {exc}") from exc

    artifact_items: dict[str, CatalogItemDTO] = {}
    artifact_by_id: dict[str, CatalogItemDTO] = {}

    for a in artifacts:
        artifact_id = a.id
        row_key = artifact_id or a.fingerprint or a.tag
        item = CatalogItemDTO(
            row_id=f"artifact:{row_key}",
            source="artifact",
            status=_norm_artifact_status(a.status.value if hasattr(a.status, "value") else str(a.status)),
            profile_id=a.profile_id,
            stack_id=a.stack_id,
            created_at=a.created_at.isoformat() if hasattr(a.created_at, "isoformat") else str(a.created_at),
            artifact_id=artifact_id,
            tag=a.tag,
            fingerprint=a.fingerprint,
            base_image=a.base_image,
            build_strategy=a.build_strategy,
            variant_json=a.variant_json,
            stale_reason=a.stale_reason,
            error_message=a.error_detail,
        )
        artifact_items[item.row_id] = item
        if artifact_id:
            artifact_by_id[artifact_id] = item

    items: list[CatalogItemDTO] = list(artifact_items.values())

    # Enrich artifact rows with job info when a job exists (for retry, log_path, etc.)
    # Do not add standalone job rows — jobs/logs are accessed via Settings.
    for j in job_rows:
        linked = artifact_by_id.get(j.result_artifact_id) if j.result_artifact_id else None
        if linked:
            linked.job_id = j.job_id
            linked.started_at = j.started_at.isoformat() if j.started_at else linked.started_at
            linked.ended_at = j.ended_at.isoformat() if j.ended_at else linked.ended_at
            linked.log_path = j.log_path
            linked.error_message = j.error_message or linked.error_message
            linked.status = _norm_artifact_status(linked.status)

    if status:
        items = [i for i in items if i.status == status]
    if profile_id:
        items = [i for i in items if i.profile_id == profile_id]
    if stack_id:
        items = [i for i in items if i.stack_id == stack_id]
    if q:
        qn = q.lower()
        items = [
            i
            for i in items
            if qn in (i.profile_id or "").lower()
            or qn in (i.stack_id or "").lower()
            or qn in (i.tag or "").lower()
            or qn in (i.fingerprint or "").lower()
        ]

    items.sort(key=_ts, reverse=True)
    return items[offset: offset + limit]
