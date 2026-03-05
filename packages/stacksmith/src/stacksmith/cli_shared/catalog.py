"""Catalog bootstrap helper for CLI flows."""

from __future__ import annotations

from stacksmith.catalog.store import CatalogStore
from stacksmith.config import AppConfig


def get_catalog() -> CatalogStore:
    cfg = AppConfig.load()
    return CatalogStore(db_path=cfg.catalog_path)
