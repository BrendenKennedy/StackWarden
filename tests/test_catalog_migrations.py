"""Tests for stackwarden.catalog.migrations."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text, inspect as sa_inspect

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
