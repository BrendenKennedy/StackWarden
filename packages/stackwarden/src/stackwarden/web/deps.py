"""FastAPI dependency injection."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from stackwarden.catalog.store import CatalogStore
from stackwarden.config import AppConfig
from stackwarden.web.auth.store import AuthStore
from stackwarden.web.jobs.manager import JobManager
from stackwarden.web.jobs.store import JobStore


@lru_cache(maxsize=1)
def _app_config() -> AppConfig:
    return AppConfig.load()


@lru_cache(maxsize=1)
def _catalog() -> CatalogStore:
    cfg = _app_config()
    return CatalogStore(db_path=cfg.catalog_path)


@lru_cache(maxsize=1)
def _job_store() -> JobStore:
    cfg = _app_config()
    return JobStore(db_path=cfg.catalog_path)


@lru_cache(maxsize=1)
def _job_manager() -> JobManager:
    return JobManager(store=_job_store())


@lru_cache(maxsize=1)
def _auth_store() -> AuthStore:
    cfg = _app_config()
    db_path = cfg.catalog_path
    if not db_path:
        data_dir = os.environ.get("STACKWARDEN_DATA_DIR")
        if data_dir:
            db_path = str(Path(data_dir) / "catalog.db")
    return AuthStore(db_path=db_path)


def get_app_config() -> AppConfig:
    return _app_config()


def get_catalog() -> CatalogStore:
    return _catalog()


def get_job_manager() -> JobManager:
    return _job_manager()


def get_auth_store() -> AuthStore:
    return _auth_store()


def reset_cached_dependencies() -> None:
    """Clear cached config/catalog/job dependencies after config updates."""
    _job_manager.cache_clear()
    _job_store.cache_clear()
    _auth_store.cache_clear()
    _catalog.cache_clear()
    _app_config.cache_clear()
