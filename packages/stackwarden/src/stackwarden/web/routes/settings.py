"""Settings endpoints for hardware catalog management."""

from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, Header, HTTPException

from stackwarden.config import AppConfig
from stackwarden.domain.block_catalog import load_block_catalog
from stackwarden.domain.hardware_catalog import load_hardware_catalog, save_hardware_catalog
from stackwarden.domain.remote_catalog import RemoteCatalogSyncResult, sync_remote_catalog
from stackwarden.domain.tuple_catalog import load_tuple_catalog
from stackwarden.web.schemas import (
    BlockPresetCatalogDTO,
    HardwareCatalogDTO,
    HardwareCatalogUpsertRequestDTO,
    SettingsConfigUpdateRequestDTO,
    SystemConfigDTO,
    TupleCatalogDTO,
)
from stackwarden.web.deps import reset_cached_dependencies
from stackwarden.web.settings import WebSettings
from stackwarden.web.util.config_dto import config_to_dto

router = APIRouter(tags=["settings"])
log = logging.getLogger(__name__)


def _require_admin_token(header_token: str | None, *, context: str = "catalog") -> None:
    """Require admin token for protected mutations. Context is used in the disabled message."""
    settings = WebSettings()
    expected = settings.admin_token
    if not expected:
        raise HTTPException(
            status_code=403,
            detail=f"{context.capitalize()} mutation disabled: set STACKWARDEN_WEB_ADMIN_TOKEN to enable.",
        )
    if not header_token or not hmac.compare_digest(header_token.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="Invalid admin token.")


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
    x_stackwarden_admin_token: str | None = Header(default=None, alias="X-StackWarden-Admin-Token"),
):
    try:
        _require_admin_token(x_stackwarden_admin_token)
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
    x_stackwarden_admin_token: str | None = Header(default=None, alias="X-StackWarden-Admin-Token"),
):
    try:
        _require_admin_token(x_stackwarden_admin_token, context="config")
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
                or "~/.local/share/stackwarden/remote-catalog"
            )
        if body.remote_catalog_local_overrides_path is not None:
            cfg.remote_catalog_local_overrides_path = (
                body.remote_catalog_local_overrides_path.strip()
                or "~/.local/share/stackwarden/local-catalog"
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
        return config_to_dto(cfg, sync_result=sync_result)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to update /settings/config")
        raise

