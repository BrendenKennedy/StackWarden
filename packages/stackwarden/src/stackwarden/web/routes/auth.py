"""Authentication endpoints for single-admin session auth."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError

from stackwarden.web.auth.session import SESSION_COOKIE_NAME, hash_session_token, parse_session_cookie
from stackwarden.web.deps import get_auth_store
from stackwarden.web.schemas import (
    AuthChangePasswordRequestDTO,
    AuthLoginRequestDTO,
    AuthSessionStatusDTO,
    AuthSetupRequestDTO,
)
from stackwarden.web.settings import WebSettings

router = APIRouter(tags=["auth"])

_SESSION_TTL_HOURS = 12
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError

    _ph = PasswordHasher()
except Exception:  # pragma: no cover - fallback for environments missing optional dependency
    class VerifyMismatchError(Exception):
        pass

    class PasswordHasher:  # type: ignore[no-redef]
        _PBKDF2_ALGO = "pbkdf2_sha256"
        _PBKDF2_ITERATIONS = 390_000

        def hash(self, value: str) -> str:
            salt = secrets.token_bytes(16)
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                value.encode(),
                salt,
                self._PBKDF2_ITERATIONS,
            )
            return f"{self._PBKDF2_ALGO}${self._PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"

        def verify(self, hashed: str, value: str) -> None:
            if hashed.startswith(f"{self._PBKDF2_ALGO}$"):
                parts = hashed.split("$")
                if len(parts) != 4:
                    raise VerifyMismatchError()
                _, iterations, salt_hex, expected_hex = parts
                try:
                    computed = hashlib.pbkdf2_hmac(
                        "sha256",
                        value.encode(),
                        bytes.fromhex(salt_hex),
                        int(iterations),
                    ).hex()
                except ValueError:
                    raise VerifyMismatchError() from None
                if not secrets.compare_digest(computed, expected_hex):
                    raise VerifyMismatchError()
                return
            # Backward-compatible verifier for older unsalted fallback hashes.
            if hashlib.sha256(value.encode()).hexdigest() != hashed:
                raise VerifyMismatchError()

    _ph = PasswordHasher()
_login_failures: dict[str, tuple[int, datetime]] = {}


def _hash_token(raw: str) -> str:
    return hash_session_token(raw)


def _issue_session(response: Response, admin_id: int) -> None:
    store = get_auth_store()
    session_id = str(uuid.uuid4())
    token_secret = secrets.token_urlsafe(48)
    session_token = f"{session_id}.{token_secret}"
    store.create_session(
        admin_id=admin_id,
        session_id=session_id,
        token_hash=_hash_token(token_secret),
        ttl_hours=_SESSION_TTL_HOURS,
    )
    settings = WebSettings()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=not settings.dev,
        samesite="lax",
        max_age=int(timedelta(hours=_SESSION_TTL_HOURS).total_seconds()),
        path="/",
    )


def _parse_session_cookie(request: Request) -> tuple[str, str] | None:
    return parse_session_cookie(request.cookies.get(SESSION_COOKIE_NAME))


def _resolve_admin(request: Request):
    parsed = _parse_session_cookie(request)
    if not parsed:
        return None
    session_id, token_secret = parsed
    return get_auth_store().validate_session(session_id, _hash_token(token_secret))


@router.get("/auth/status", response_model=AuthSessionStatusDTO)
async def auth_status(request: Request):
    store = get_auth_store()
    has_admin = store.has_admin()
    if not has_admin:
        return AuthSessionStatusDTO(setup_required=True, authenticated=False, username=None)
    admin = _resolve_admin(request)
    if not admin:
        return AuthSessionStatusDTO(setup_required=False, authenticated=False, username=None)
    return AuthSessionStatusDTO(setup_required=False, authenticated=True, username=admin.username)


@router.post("/auth/setup", response_model=AuthSessionStatusDTO)
async def auth_setup(body: AuthSetupRequestDTO, response: Response):
    store = get_auth_store()
    if store.has_admin():
        raise HTTPException(status_code=409, detail="Admin account already initialized.")
    username = body.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")
    if len(body.password) < 10:
        raise HTTPException(status_code=400, detail="Password must be at least 10 characters.")
    try:
        admin = store.create_admin(username=username, password_hash=_ph.hash(body.password))
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Admin account already initialized.") from None
    _issue_session(response, admin.id)
    return AuthSessionStatusDTO(setup_required=False, authenticated=True, username=admin.username)


@router.post("/auth/login", response_model=AuthSessionStatusDTO)
async def auth_login(body: AuthLoginRequestDTO, request: Request, response: Response):
    store = get_auth_store()
    if not store.has_admin():
        raise HTTPException(status_code=400, detail="Admin setup required before login.")

    client_ip = request.client.host if request.client else "unknown"
    attempts, blocked_until = _login_failures.get(client_ip, (0, datetime.fromtimestamp(0, tz=timezone.utc)))
    now = datetime.now(timezone.utc)
    if blocked_until > now:
        wait_s = int((blocked_until - now).total_seconds())
        raise HTTPException(status_code=429, detail=f"Too many attempts. Retry in {wait_s}s.")

    admin = store.get_admin_by_username(body.username.strip())
    if not admin:
        _login_failures[client_ip] = (attempts + 1, now + timedelta(seconds=min(30, (attempts + 1) * 2)))
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    try:
        _ph.verify(admin.password_hash, body.password)
    except VerifyMismatchError:
        _login_failures[client_ip] = (attempts + 1, now + timedelta(seconds=min(30, (attempts + 1) * 2)))
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    _login_failures.pop(client_ip, None)
    _issue_session(response, admin.id)
    return AuthSessionStatusDTO(setup_required=False, authenticated=True, username=admin.username)


@router.post("/auth/logout")
async def auth_logout(request: Request, response: Response):
    parsed = _parse_session_cookie(request)
    if parsed:
        session_id, _ = parsed
        get_auth_store().revoke_session(session_id)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"ok": True}


@router.post("/auth/change-password")
async def auth_change_password(body: AuthChangePasswordRequestDTO, request: Request, response: Response):
    admin = _resolve_admin(request)
    if not admin:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    if len(body.new_password) < 10:
        raise HTTPException(status_code=400, detail="New password must be at least 10 characters.")
    try:
        _ph.verify(admin.password_hash, body.current_password)
    except VerifyMismatchError:
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    store = get_auth_store()
    store.update_password(admin.id, _ph.hash(body.new_password))
    store.revoke_all_sessions(admin.id)
    _issue_session(response, admin.id)
    return {"ok": True}


