"""Verify endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from stackwarden.catalog.store import CatalogStore
from stackwarden.domain.verify import apply_fix, verify_artifact
from stackwarden.runtime.docker_client import DockerClient
from stackwarden.web.deps import get_catalog
from stackwarden.web.schemas import VerifyRequestDTO, VerifyResponseDTO

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
