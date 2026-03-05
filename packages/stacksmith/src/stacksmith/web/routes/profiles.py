"""Profile endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Response

from stacksmith.application.create_flows import (
    AppNotFoundError,
    AppValidationError,
    update_profile as app_update_profile,
)
from stacksmith.config import (
    get_profile_origin,
    get_profiles_dir,
    list_profile_ids,
    load_profile,
)
from stacksmith.domain.errors import ProfileNotFoundError
from stacksmith.web.schemas import (
    ProfileCreateRequest,
    ProfileCreateResponse,
    ProfileDetailDTO,
    ProfileSummaryDTO,
)
from stacksmith.web.util.versioning import apply_version_headers, resolve_schema_version
from stacksmith.web.util.write_yaml import serialize_for_yaml

router = APIRouter(tags=["profiles"])
log = logging.getLogger(__name__)


def _validation_422(errors: list[dict[str, str]]):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=422, content={"detail": errors})


@router.get("/profiles", response_model=list[ProfileSummaryDTO])
async def list_profiles(response: Response, schema: str | None = Query(default=None)):
    try:
        apply_version_headers(response, requested=resolve_schema_version(schema))
        profiles = []
        skipped = 0
        for pid in list_profile_ids():
            try:
                profiles.append(load_profile(pid))
            except Exception as exc:  # noqa: BLE001 - keep listing resilient
                skipped += 1
                log.warning("Skipping invalid profile during list: id=%s error=%s", pid, exc)
        if skipped:
            response.headers["X-Stacksmith-Profiles-Skipped"] = str(skipped)
        return [ProfileSummaryDTO.from_domain(p, origin=get_profile_origin(p.id)) for p in profiles]
    except Exception:
        log.exception("Failed to list profiles")
        raise


@router.get("/profiles/{profile_id}", response_model=ProfileDetailDTO)
async def get_profile(profile_id: str, response: Response, schema: str | None = Query(default=None)):
    try:
        apply_version_headers(response, requested=resolve_schema_version(schema))
        try:
            profile = load_profile(profile_id)
        except ProfileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}")
        return ProfileDetailDTO.from_domain(profile, origin=get_profile_origin(profile.id))
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to get profile: %s", profile_id)
        raise


@router.get("/profiles/{profile_id}/spec")
async def get_profile_spec(profile_id: str):
    try:
        try:
            profile = load_profile(profile_id)
        except ProfileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}")
        return serialize_for_yaml(profile)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to get profile spec: %s", profile_id)
        raise


@router.put("/profiles/{profile_id}", response_model=ProfileCreateResponse)
async def update_profile(profile_id: str, req: ProfileCreateRequest):
    try:
        target = app_update_profile(profile_id, req)
        return ProfileCreateResponse(id=profile_id, display_name=req.display_name, path=str(target))
    except AppValidationError as exc:
        return _validation_422(exc.errors)
    except AppNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to update profile: %s", profile_id)
        raise


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    try:
        profiles_dir = get_profiles_dir()
        target = (profiles_dir / f"{profile_id}.yaml").resolve()
        if not target.is_relative_to(profiles_dir.resolve()):
            raise HTTPException(status_code=400, detail=f"Invalid profile id: {profile_id}")
        if not target.exists():
            raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}")
        target.unlink()
        return {"deleted": True, "id": profile_id}
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to delete profile: %s", profile_id)
        raise
