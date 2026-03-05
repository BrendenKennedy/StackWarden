"""Simple forward-only migration runner for the catalog schema.

SQLAlchemy's ``create_all`` handles initial table creation.  This module
provides versioned ALTER statements for schema evolution after the initial
release.  Each migration is idempotent.
"""

from __future__ import annotations

import logging
from sqlalchemy import text, inspect as sa_inspect
from sqlalchemy.engine import Engine

log = logging.getLogger(__name__)


def _column_exists(engine: Engine, table: str, column: str) -> bool:
    inspector = sa_inspect(engine)
    columns = [c["name"] for c in inspector.get_columns(table)]
    return column in columns


def _index_exists(engine: Engine, table: str, index_name: str) -> bool:
    inspector = sa_inspect(engine)
    indexes = inspector.get_indexes(table)
    return any(idx["name"] == index_name for idx in indexes)


_MIGRATIONS: list[tuple[str, str, list[str]]] = [
    # (description, guard_table, statements)
    # v0.2: add template_hash and stack_schema_version if missing
    (
        "add template_hash to artifacts",
        "artifacts",
        [
            "ALTER TABLE artifacts ADD COLUMN template_hash TEXT",
        ],
    ),
    (
        "add stack_schema_version to artifacts",
        "artifacts",
        [
            "ALTER TABLE artifacts ADD COLUMN stack_schema_version INTEGER DEFAULT 1",
        ],
    ),
    (
        "add profile_schema_version to artifacts",
        "artifacts",
        [
            "ALTER TABLE artifacts ADD COLUMN profile_schema_version INTEGER DEFAULT 1",
        ],
    ),
    (
        "add block_schema_version to artifacts",
        "artifacts",
        [
            "ALTER TABLE artifacts ADD COLUMN block_schema_version INTEGER DEFAULT 1",
        ],
    ),
    # Day-2: drift detection
    (
        "add stale_reason to artifacts",
        "artifacts",
        [
            "ALTER TABLE artifacts ADD COLUMN stale_reason TEXT",
        ],
    ),
    # Day-2: manifest
    (
        "add manifest_path to artifacts",
        "artifacts",
        [
            "ALTER TABLE artifacts ADD COLUMN manifest_path TEXT",
        ],
    ),
    # Day-2: SBOM
    (
        "add sbom_path to artifacts",
        "artifacts",
        [
            "ALTER TABLE artifacts ADD COLUMN sbom_path TEXT",
        ],
    ),
    # Day-2: variants
    (
        "add variant_json to artifacts",
        "artifacts",
        [
            "ALTER TABLE artifacts ADD COLUMN variant_json TEXT",
        ],
    ),
    # Spec snapshots
    (
        "add profile_snapshot_path to artifacts",
        "artifacts",
        [
            "ALTER TABLE artifacts ADD COLUMN profile_snapshot_path TEXT",
        ],
    ),
    (
        "add stack_snapshot_path to artifacts",
        "artifacts",
        [
            "ALTER TABLE artifacts ADD COLUMN stack_snapshot_path TEXT",
        ],
    ),
    (
        "add plan_path to artifacts",
        "artifacts",
        [
            "ALTER TABLE artifacts ADD COLUMN plan_path TEXT",
        ],
    ),
    # Day-2: provenance
    (
        "add host_id to artifacts",
        "artifacts",
        [
            "ALTER TABLE artifacts ADD COLUMN host_id TEXT",
        ],
    ),
    (
        "add docker_context to artifacts",
        "artifacts",
        [
            "ALTER TABLE artifacts ADD COLUMN docker_context TEXT",
        ],
    ),
    (
        "add daemon_arch to artifacts",
        "artifacts",
        [
            "ALTER TABLE artifacts ADD COLUMN daemon_arch TEXT",
        ],
    ),
]


_INDEX_MIGRATIONS: list[tuple[str, str, str]] = [
    # (description, table, CREATE INDEX statement)
    (
        "unique index on artifacts.fingerprint",
        "artifacts",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_artifacts_fingerprint_unique "
        "ON artifacts(fingerprint)",
    ),
]


def run_migrations(engine: Engine) -> None:
    """Apply any pending migrations."""
    for desc, table, stmts in _MIGRATIONS:
        for stmt in stmts:
            col = stmt.split("ADD COLUMN ")[-1].split()[0]
            if _column_exists(engine, table, col):
                continue
            log.info("Migration: %s", desc)
            with engine.begin() as conn:
                conn.execute(text(stmt))

    for desc, table, stmt in _INDEX_MIGRATIONS:
        idx_name = stmt.split("EXISTS ")[-1].split()[0]
        if _index_exists(engine, table, idx_name):
            continue
        log.info("Migration: %s", desc)
        with engine.begin() as conn:
            conn.execute(text(stmt))
