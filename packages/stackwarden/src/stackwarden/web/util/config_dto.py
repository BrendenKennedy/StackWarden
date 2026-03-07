"""Shared config-to-DTO mapping for system and settings endpoints."""

from __future__ import annotations

from stackwarden.config import AppConfig, tuple_layer_mode
from stackwarden.paths import get_catalog_path, get_logs_root
from stackwarden.web.deps import get_auth_store
from stackwarden.web.schemas import SystemConfigDTO
from stackwarden.web.settings import WebSettings


def config_to_dto(
    cfg: AppConfig,
) -> SystemConfigDTO:
    """Build SystemConfigDTO from AppConfig."""
    effective_catalog_path = str(cfg.catalog_path or get_catalog_path())
    effective_log_dir = str(cfg.log_dir or get_logs_root())
    settings = WebSettings()
    return SystemConfigDTO(
        catalog_path=effective_catalog_path,
        log_dir=effective_log_dir,
        default_profile=cfg.default_profile,
        registry_allow=cfg.registry.allow,
        registry_deny=cfg.registry.deny,
        catalog_local_path=cfg.catalog_local_path,
        catalog_local_overrides_path=cfg.catalog_local_overrides_path,
        auth_enabled=get_auth_store().has_admin(),
        blocks_first_enabled=settings.blocks_first_enabled,
        tuple_layer_mode=tuple_layer_mode(),
    )
