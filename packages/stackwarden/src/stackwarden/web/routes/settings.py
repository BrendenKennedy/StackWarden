"""Settings endpoints for hardware catalog management."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException

from stackwarden.config import AppConfig
from stackwarden.domain.block_catalog import load_layer_catalog
from stackwarden.domain.hardware_catalog import load_hardware_catalog, save_hardware_catalog
from stackwarden.domain.tuple_catalog import load_tuple_catalog
from stackwarden.web.schemas import (
    LayerPresetCatalogDTO,
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


def _resolve_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "Makefile").exists() and (parent / "ops" / "scripts" / "recycle_services.sh").exists():
            return parent
    raise RuntimeError("Unable to resolve repository root for service recycle.")


def _start_recycle_process(repo_root: Path) -> dict[str, object]:
    script = repo_root / "ops" / "scripts" / "recycle_services.sh"
    log_file = repo_root / ".stackwarden" / "logs" / "recycle-from-ui.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handle = open(log_file, "a", encoding="utf-8")
    process = subprocess.Popen(
        [str(script)],
        cwd=repo_root,
        stdout=handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    handle.close()
    return {"started": True, "pid": process.pid, "log_file": str(log_file)}


@router.get("/settings/hardware-catalogs", response_model=HardwareCatalogDTO)
async def get_hardware_catalogs():
    try:
        return HardwareCatalogDTO.model_validate(load_hardware_catalog().model_dump(mode="json"))
    except Exception:
        log.exception("Failed to serve /settings/hardware-catalogs")
        raise


@router.get("/settings/layer-catalog", response_model=LayerPresetCatalogDTO)
async def get_layer_catalog():
    try:
        return LayerPresetCatalogDTO.model_validate(load_layer_catalog().model_dump(mode="json"))
    except Exception:
        log.exception("Failed to serve /settings/layer-catalog")
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
):
    try:
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
):
    try:
        cfg = AppConfig.load()

        if body.default_profile is not None:
            cfg.default_profile = body.default_profile or None
        if body.registry_allow is not None:
            cfg.registry.allow = [v.strip() for v in body.registry_allow if v.strip()]
        if body.registry_deny is not None:
            cfg.registry.deny = [v.strip() for v in body.registry_deny if v.strip()]
        if body.catalog_local_path is not None:
            cfg.catalog_local_path = body.catalog_local_path.strip() or None
        if body.catalog_local_overrides_path is not None:
            cfg.catalog_local_overrides_path = body.catalog_local_overrides_path.strip() or None
        if body.tuple_layer_mode is not None:
            mode = body.tuple_layer_mode.strip().lower()
            cfg.tuple_layer_mode = mode if mode in {"off", "shadow", "warn", "enforce"} else "enforce"

        cfg.save()
        reset_cached_dependencies()
        return config_to_dto(cfg)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to update /settings/config")
        raise


@router.post("/settings/services/recycle")
async def recycle_services():
    try:
        settings = WebSettings()
        if not settings.dev:
            raise HTTPException(status_code=403, detail="Service recycle endpoint is available in dev mode only.")

        repo_root = _resolve_repo_root()
        return _start_recycle_process(repo_root)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to start service recycle from settings endpoint")
        raise


