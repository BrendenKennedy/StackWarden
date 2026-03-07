"""Tests for stackwarden.catalog.migrations."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from stackwarden.catalog.migrations import _column_exists, _index_exists, run_migrations


@pytest.fixture()
def engine(tmp_path):
    db_path = tmp_path / "test.db"
    eng = create_engine(f"sqlite:///{db_path}")
    with eng.begin() as conn:
        conn.execute(text(
            "CREATE TABLE artifacts ("
            "  id INTEGER PRIMARY KEY,"
            "  fingerprint TEXT,"
            "  tag TEXT"
            ")"
        ))
    return eng


class TestColumnExists:
    def test_returns_true_for_existing(self, engine):
        assert _column_exists(engine, "artifacts", "fingerprint") is True

    def test_returns_false_for_missing(self, engine):
        assert _column_exists(engine, "artifacts", "nonexistent") is False


class TestIndexExists:
    def test_returns_false_before_creation(self, engine):
        assert _index_exists(engine, "artifacts", "idx_artifacts_fingerprint_unique") is False

    def test_returns_true_after_creation(self, engine):
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE UNIQUE INDEX idx_artifacts_fingerprint_unique ON artifacts(fingerprint)"
            ))
        assert _index_exists(engine, "artifacts", "idx_artifacts_fingerprint_unique") is True


class TestRunMigrations:
    def test_adds_missing_columns(self, engine):
        assert _column_exists(engine, "artifacts", "template_hash") is False
        run_migrations(engine)
        assert _column_exists(engine, "artifacts", "template_hash") is True
        assert _column_exists(engine, "artifacts", "variant_json") is True
        assert _column_exists(engine, "artifacts", "sbom_path") is True

    def test_idempotent(self, engine):
        run_migrations(engine)
        run_migrations(engine)
        assert _column_exists(engine, "artifacts", "template_hash") is True

    def test_creates_fingerprint_index(self, engine):
        run_migrations(engine)
        assert _index_exists(engine, "artifacts", "idx_artifacts_fingerprint_unique") is True

    def test_backfills_layer_schema_version_from_legacy_block_column(self, engine):
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE artifacts ADD COLUMN block_schema_version INTEGER DEFAULT 1"
            ))
            conn.execute(text(
                "ALTER TABLE artifacts ADD COLUMN layer_schema_version INTEGER DEFAULT 1"
            ))
            conn.execute(text(
                "INSERT INTO artifacts (id, fingerprint, tag, block_schema_version, layer_schema_version) "
                "VALUES (1, 'fp-1', 'tag-1', 2, 1)"
            ))

        run_migrations(engine)

        with engine.begin() as conn:
            row = conn.execute(text(
                "SELECT layer_schema_version, block_schema_version FROM artifacts WHERE id = 1"
            )).first()
        assert row is not None
        assert row[0] == 2
        assert row[1] == 2
