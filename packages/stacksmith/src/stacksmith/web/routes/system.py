"""System / config endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from stacksmith.config import AppConfig, tuple_layer_mode
from stacksmith.paths import get_catalog_path, get_logs_root
from stacksmith.web.deps import get_app_config
from stacksmith.web.schemas import SystemConfigDTO
from stacksmith.web.settings import WebSettings

router = APIRouter(tags=["system"])
log = logging.getLogger(__name__)


@router.get("/system/config", response_model=SystemConfigDTO)
async def system_config(cfg: AppConfig = Depends(get_app_config)):
    try:
        catalog_path = str(cfg.catalog_path or get_catalog_path())
        log_dir = str(cfg.log_dir or get_logs_root())
        settings = WebSettings()
        return SystemConfigDTO(
            catalog_path=catalog_path,
            log_dir=log_dir,
            default_profile=cfg.default_profile,
            registry_allow=cfg.registry.allow,
            registry_deny=cfg.registry.deny,
            remote_catalog_enabled=cfg.remote_catalog_enabled,
            remote_catalog_repo_url=cfg.remote_catalog_repo_url,
            remote_catalog_branch=cfg.remote_catalog_branch,
            remote_catalog_local_path=cfg.remote_catalog_local_path,
            remote_catalog_local_overrides_path=cfg.remote_catalog_local_overrides_path,
            remote_catalog_auto_pull=cfg.remote_catalog_auto_pull,
            auth_enabled=settings.token is not None,
            blocks_first_enabled=settings.blocks_first_enabled,
            tuple_layer_mode=tuple_layer_mode(),
        )
    except Exception:
        log.exception("Failed to serve /system/config")
        raise
