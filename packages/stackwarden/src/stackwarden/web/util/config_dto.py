"""Shared config-to-DTO mapping for system and settings endpoints."""

from __future__ import annotations

from stackwarden.config import AppConfig, tuple_layer_mode
from stackwarden.domain.remote_catalog import RemoteCatalogSyncResult
from stackwarden.paths import get_catalog_path, get_logs_root
from stackwarden.web.schemas import SystemConfigDTO
from stackwarden.web.settings import WebSettings


def config_to_dto(
    cfg: AppConfig,
    sync_result: RemoteCatalogSyncResult | None = None,
) -> SystemConfigDTO:
    """Build SystemConfigDTO from AppConfig, optionally including remote catalog sync status."""
    effective_catalog_path = str(cfg.catalog_path or get_catalog_path())
    effective_log_dir = str(cfg.log_dir or get_logs_root())
    settings = WebSettings()
    return SystemConfigDTO(
        catalog_path=effective_catalog_path,
        log_dir=effective_log_dir,
        default_profile=cfg.default_profile,
        registry_allow=cfg.registry.allow,
        registry_deny=cfg.registry.deny,
        remote_catalog_enabled=cfg.remote_catalog_enabled,
        remote_catalog_repo_url=cfg.remote_catalog_repo_url,
        remote_catalog_branch=cfg.remote_catalog_branch,
        remote_catalog_local_path=cfg.remote_catalog_local_path,
        remote_catalog_local_overrides_path=cfg.remote_catalog_local_overrides_path,
        remote_catalog_auto_pull=cfg.remote_catalog_auto_pull,
        remote_catalog_last_sync_status=sync_result.status if sync_result else None,
        remote_catalog_last_sync_detail=sync_result.detail if sync_result else None,
        remote_catalog_last_sync_commit=sync_result.commit if sync_result else None,
        auth_enabled=settings.token is not None,
        blocks_first_enabled=settings.blocks_first_enabled,
        tuple_layer_mode=tuple_layer_mode(),
    )
