"""Verify endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from stacksmith.catalog.store import CatalogStore
from stacksmith.domain.verify import apply_fix, verify_artifact
from stacksmith.runtime.docker_client import DockerClient
from stacksmith.web.deps import get_catalog
from stacksmith.web.schemas import VerifyRequestDTO, VerifyResponseDTO

router = APIRouter(tags=["verify"])


@router.post("/verify", response_model=VerifyResponseDTO)
def verify(
    body: VerifyRequestDTO,
    catalog: CatalogStore = Depends(get_catalog),
):
    try:
        docker = DockerClient()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Docker not available: {exc}")

    report = verify_artifact(
        body.tag_or_id,
        docker,
        catalog,
        strict=body.strict,
    )

    actions: list[str] = []
    if body.fix and not report.ok:
        actions = apply_fix(body.tag_or_id, report, catalog)

    return VerifyResponseDTO.from_domain(report, actions=actions)
