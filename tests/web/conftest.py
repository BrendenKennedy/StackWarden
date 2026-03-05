"""Shared fixtures for web API tests."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def data_dir(tmp_path):
    """Temporary data directory with stacks/, profiles/, and blocks/ subdirs."""
    for name in ("stacks", "profiles", "blocks"):
        (tmp_path / name).mkdir()
    return tmp_path


@pytest.fixture()
def client(data_dir):
    """TestClient backed by a fresh app writing specs to *data_dir*."""
    with patch.dict(
        os.environ,
        {"STACKWARDEN_DATA_DIR": str(data_dir), "STACKWARDEN_WEB_DEV": "true"},
    ):
        from stackwarden.web.app import create_app
        from stackwarden.web.settings import WebSettings

        app = create_app(WebSettings(token=None, dev=True))
        yield TestClient(app)
