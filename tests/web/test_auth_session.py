from __future__ import annotations

import os
import time
from contextlib import contextmanager
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError


@contextmanager
def _client(tmp_path):
    for name in ("stacks", "profiles", "blocks"):
        (tmp_path / name).mkdir(exist_ok=True)
    with patch.dict(
        os.environ,
        {"STACKWARDEN_DATA_DIR": str(tmp_path), "STACKWARDEN_WEB_DEV": "true"},
    ):
        from stackwarden.web.app import create_app
        from stackwarden.web.deps import reset_cached_dependencies
        from stackwarden.web.settings import WebSettings

        reset_cached_dependencies()
        with TestClient(create_app(WebSettings(token=None, dev=True))) as client:
            yield client


def test_requires_setup_before_protected_access(tmp_path):
    with _client(tmp_path) as client:
        status = client.get("/api/auth/status")
        assert status.status_code == 200
        assert status.json()["setup_required"] is True

        protected = client.get("/api/system/config")
        assert protected.status_code == 403


def test_setup_login_logout_and_change_password_flow(tmp_path):
    with _client(tmp_path) as client:
        setup = client.post(
            "/api/auth/setup",
            json={"username": "admin", "password": "super-secure-pass"},
        )
        assert setup.status_code == 200
        assert setup.json()["authenticated"] is True

        status = client.get("/api/auth/status")
        assert status.status_code == 200
        assert status.json()["authenticated"] is True

        logout = client.post("/api/auth/logout")
        assert logout.status_code == 200

        status_after_logout = client.get("/api/auth/status")
        assert status_after_logout.status_code == 200
        assert status_after_logout.json()["authenticated"] is False

        bad_login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong-password"},
        )
        assert bad_login.status_code == 401

        good_login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "super-secure-pass"},
        )
        if good_login.status_code == 429:
            time.sleep(2)
            good_login = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "super-secure-pass"},
            )
        assert good_login.status_code == 200

        change = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "super-secure-pass",
                "new_password": "new-secure-pass-123",
            },
        )
        assert change.status_code == 200

        client.post("/api/auth/logout")

        old_password_login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "super-secure-pass"},
        )
        assert old_password_login.status_code == 401

        new_password_login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "new-secure-pass-123"},
        )
        if new_password_login.status_code == 429:
            time.sleep(2)
            new_password_login = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "new-secure-pass-123"},
            )
        assert new_password_login.status_code == 200


def test_reset_admin_endpoint_not_available(tmp_path):
    with _client(tmp_path) as client:
        setup = client.post(
            "/api/auth/setup",
            json={"username": "admin", "password": "super-secure-pass"},
        )
        assert setup.status_code == 200

        reset = client.post("/api/auth/reset-admin", json={"confirmation_phrase": "RESET ADMIN"})
        assert reset.status_code in {401, 404, 405}


def test_setup_integrity_error_returns_conflict(tmp_path, monkeypatch):
    with _client(tmp_path) as client:
        from stackwarden.web.routes import auth as auth_routes

        store = auth_routes.get_auth_store()
        monkeypatch.setattr(store, "has_admin", lambda: False)

        def _raise_integrity_error(*args, **kwargs):
            raise IntegrityError("insert", {}, Exception("unique constraint"))

        monkeypatch.setattr(store, "create_admin", _raise_integrity_error)

        setup = client.post(
            "/api/auth/setup",
            json={"username": "admin", "password": "super-secure-pass"},
        )
        assert setup.status_code == 409
        assert setup.json()["detail"] == "Admin account already initialized."
