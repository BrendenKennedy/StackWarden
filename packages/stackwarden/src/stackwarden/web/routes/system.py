"""System / config endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from stackwarden.config import AppConfig
from stackwarden.web.deps import get_app_config
from stackwarden.web.schemas import SystemConfigDTO
from stackwarden.web.util.config_dto import config_to_dto

router = APIRouter(tags=["system"])
log = logging.getLogger(__name__)


@router.get("/system/config", response_model=SystemConfigDTO)
async def system_config(cfg: AppConfig = Depends(get_app_config)):
    try:
        return config_to_dto(cfg)
    except Exception:
        log.exception("Failed to serve /system/config")
        raise
