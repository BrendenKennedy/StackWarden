"""Tests for the init command and AppConfig wiring."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from stackwarden.config import AppConfig


class TestAppConfig:
    def test_load_returns_defaults_when_missing(self, tmp_path):
        fake_path = tmp_path / "nonexistent.yaml"
        with patch("stackwarden.config.get_config_path", return_value=fake_path):
            cfg = AppConfig.load()
            assert cfg.default_profile is None
            assert cfg.catalog_path is None

    def test_load_reads_existing(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump({
            "default_profile": "x86_cuda",
            "catalog_path": "/custom/catalog.db",
            "registry": {"allow": ["nvcr.io"], "deny": []},
        }))
        with patch("stackwarden.config.get_config_path", return_value=config_path):
            cfg = AppConfig.load()
            assert cfg.default_profile == "x86_cuda"
            assert cfg.catalog_path == "/custom/catalog.db"
            assert "nvcr.io" in cfg.registry.allow

    def test_round_trip_default_config(self, tmp_path):
        """The default config written by init should load cleanly."""
        config_path = tmp_path / "config.yaml"
        default_config = (
            "# StackWarden configuration\n"
            "# See: stackwarden doctor\n"
            "\n"
            "# default_profile: x86_cuda\n"
            "# catalog_path: null\n"
            "# log_dir: null\n"
            "\n"
            "registry:\n"
            "  allow:\n"
            '    - "nvcr.io"\n'
            '    - "docker.io"\n'
            "  deny: []\n"
        )
        config_path.write_text(default_config)
        with patch("stackwarden.config.get_config_path", return_value=config_path):
            cfg = AppConfig.load()
            assert cfg.default_profile is None
            assert "nvcr.io" in cfg.registry.allow
            assert "docker.io" in cfg.registry.allow


class TestInitDirectories:
    def test_creates_all_dirs_via_init_command(self, tmp_path):
        """Exercise the actual CLI init command to verify directory creation."""
        from typer.testing import CliRunner
        from stackwarden.cli import app

        data_root = tmp_path / "data"
        config_root = tmp_path / "config"

        with (
            patch("stackwarden.paths._data_root", return_value=data_root),
            patch("stackwarden.paths._config_root", return_value=config_root),
        ):
            runner = CliRunner()
            result = runner.invoke(app, ["init"])
            assert result.exit_code == 0, result.output

            assert (data_root).exists()
            assert (data_root / "artifacts").exists()
            assert (data_root / "logs").exists()
            assert (data_root / "locks").exists()
            assert config_root.exists()

    def test_init_idempotent(self, tmp_path):
        """Running init twice does not fail."""
        from typer.testing import CliRunner
        from stackwarden.cli import app

        data_root = tmp_path / "data"
        config_root = tmp_path / "config"

        with (
            patch("stackwarden.paths._data_root", return_value=data_root),
            patch("stackwarden.paths._config_root", return_value=config_root),
        ):
            runner = CliRunner()
            result1 = runner.invoke(app, ["init"])
            assert result1.exit_code == 0
            result2 = runner.invoke(app, ["init"])
            assert result2.exit_code == 0


class TestGetCatalog:
    def test_default_path(self, tmp_path):
        with patch("stackwarden.paths._data_root", return_value=tmp_path):
            from stackwarden.catalog.store import CatalogStore
            store = CatalogStore()
            assert (tmp_path / "catalog.db").exists()

    def test_custom_path(self, tmp_path):
        custom_db = tmp_path / "custom.db"
        from stackwarden.catalog.store import CatalogStore
        store = CatalogStore(db_path=custom_db)
        assert custom_db.exists()
