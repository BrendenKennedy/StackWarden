"""Settings endpoints for hardware catalog management."""

from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, Header, HTTPException

from stacksmith.config import AppConfig, tuple_layer_mode
from stacksmith.domain.block_catalog import load_block_catalog
from stacksmith.domain.hardware_catalog import load_hardware_catalog, save_hardware_catalog
from stacksmith.domain.remote_catalog import RemoteCatalogSyncResult, sync_remote_catalog
from stacksmith.domain.tuple_catalog import load_tuple_catalog
from stacksmith.paths import get_catalog_path, get_logs_root
from stacksmith.web.schemas import (
    BlockPresetCatalogDTO,
    HardwareCatalogDTO,
    HardwareCatalogUpsertRequestDTO,
    SettingsConfigUpdateRequestDTO,
    SystemConfigDTO,
    TupleCatalogDTO,
)
from stacksmith.web.deps import reset_cached_dependencies
from stacksmith.web.settings import WebSettings

router = APIRouter(tags=["settings"])
log = logging.getLogger(__name__)


def _require_admin_token(header_token: str | None) -> None:
    settings = WebSettings()
    expected = settings.admin_token
    if not expected:
        raise HTTPException(
            status_code=403,
            detail="Catalog mutation disabled: set STACKSMITH_WEB_ADMIN_TOKEN to enable.",
        )
    if not header_token or not hmac.compare_digest(header_token.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="Invalid admin token.")


def _require_config_admin_token(header_token: str | None) -> None:
    """Require admin token for config mutations."""
    settings = WebSettings()
    expected = settings.admin_token
    if not expected:
        raise HTTPException(
            status_code=403,
            detail="Config mutation disabled: set STACKSMITH_WEB_ADMIN_TOKEN to enable.",
        )
    if not header_token or not hmac.compare_digest(header_token.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="Invalid admin token.")


def _config_to_dto(
    cfg: AppConfig,
    sync_result: RemoteCatalogSyncResult | None = None,
) -> SystemConfigDTO:
    effective_catalog_path = str(cfg.catalog_path or get_catalog_path())
    effective_log_dir = str(cfg.log_dir or get_logs_root())
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
        auth_enabled=WebSettings().token is not None,
        blocks_first_enabled=WebSettings().blocks_first_enabled,
        tuple_layer_mode=tuple_layer_mode(),
    )


@router.get("/settings/hardware-catalogs", response_model=HardwareCatalogDTO)
async def get_hardware_catalogs():
    try:
        return HardwareCatalogDTO.model_validate(load_hardware_catalog().model_dump(mode="json"))
    except Exception:
        log.exception("Failed to serve /settings/hardware-catalogs")
        raise


@router.get("/settings/block-catalog", response_model=BlockPresetCatalogDTO)
async def get_block_catalog():
    try:
        return BlockPresetCatalogDTO.model_validate(load_block_catalog().model_dump(mode="json"))
    except Exception:
        log.exception("Failed to serve /settings/block-catalog")
        raise


@router.get("/settings/tuple-catalog", response_model=TupleCatalogDTO)
async def get_tuple_catalog():
    try:
        return TupleCatalogDTO.model_validate(load_tuple_catalog().model_dump(mode="json"))
    except Exception:
        log.exception("Failed to serve /settings/tuple-catalog")
        raise


@router.post("/settings/hardware-catalogs/{catalog}", response_model=HardwareCatalogDTO)
async def upsert_hardware_catalog_item(
    catalog: str,
    body: HardwareCatalogUpsertRequestDTO,
    x_stacksmith_admin_token: str | None = Header(default=None, alias="X-Stacksmith-Admin-Token"),
):
    try:
        _require_admin_token(x_stacksmith_admin_token)
        if body.catalog != catalog:
            raise HTTPException(status_code=400, detail="Catalog path/body mismatch.")

        existing = load_hardware_catalog()
        if not hasattr(existing, catalog):
            raise HTTPException(status_code=404, detail=f"Unknown catalog: {catalog}")

        items = list(getattr(existing, catalog))
        idx = next((i for i, item in enumerate(items) if item.id == body.item.id), -1)
        if idx >= 0:
            items[idx] = body.item
        else:
            items.append(body.item)
        updated = existing.model_copy(update={catalog: items})
        saved = save_hardware_catalog(updated, expected_revision=body.expected_revision)
        return HardwareCatalogDTO.model_validate(saved.model_dump(mode="json"))
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to upsert /settings/hardware-catalogs/%s", catalog)
        raise


@router.post("/settings/config", response_model=SystemConfigDTO)
async def update_settings_config(
    body: SettingsConfigUpdateRequestDTO,
    x_stacksmith_admin_token: str | None = Header(default=None, alias="X-Stacksmith-Admin-Token"),
):
    try:
        _require_config_admin_token(x_stacksmith_admin_token)
        cfg = AppConfig.load()

        if body.default_profile is not None:
            cfg.default_profile = body.default_profile or None
        if body.registry_allow is not None:
            cfg.registry.allow = [v.strip() for v in body.registry_allow if v.strip()]
        if body.registry_deny is not None:
            cfg.registry.deny = [v.strip() for v in body.registry_deny if v.strip()]
        if body.remote_catalog_enabled is not None:
            cfg.remote_catalog_enabled = body.remote_catalog_enabled
        if body.remote_catalog_repo_url is not None:
            cfg.remote_catalog_repo_url = body.remote_catalog_repo_url.strip() or None
        if body.remote_catalog_branch is not None:
            cfg.remote_catalog_branch = body.remote_catalog_branch.strip() or "main"
        if body.remote_catalog_local_path is not None:
            cfg.remote_catalog_local_path = (
                body.remote_catalog_local_path.strip()
                or "~/.local/share/stacksmith/remote-catalog"
            )
        if body.remote_catalog_local_overrides_path is not None:
            cfg.remote_catalog_local_overrides_path = (
                body.remote_catalog_local_overrides_path.strip()
                or "~/.local/share/stacksmith/local-catalog"
            )
        if body.remote_catalog_auto_pull is not None:
            cfg.remote_catalog_auto_pull = body.remote_catalog_auto_pull
        if body.tuple_layer_mode is not None:
            mode = body.tuple_layer_mode.strip().lower()
            cfg.tuple_layer_mode = mode if mode in {"off", "shadow", "warn", "enforce"} else "enforce"

        sync_result: RemoteCatalogSyncResult | None = None
        if body.sync_now:
            sync_result = sync_remote_catalog(cfg)

        cfg.save()
        reset_cached_dependencies()
        return _config_to_dto(cfg, sync_result=sync_result)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to update /settings/config")
        raise

