"""FastAPI application factory for the StackWarden Web UI."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from stackwarden.web.auth.session import SESSION_COOKIE_NAME, hash_session_token, parse_session_cookie
from stackwarden.web.deps import get_auth_store
from stackwarden.web.settings import WebSettings

log = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"


def _format_validation_field(loc: tuple[object, ...] | list[object]) -> str:
    parts = [str(part) for part in loc if str(part) not in {"body", "query", "path"}]
    return ".".join(parts) if parts else "request"


# ---------------------------------------------------------------------------
# Session auth middleware
# ---------------------------------------------------------------------------


class SessionAuthMiddleware(BaseHTTPMiddleware):
    """Enforce authenticated admin sessions for protected API routes.

    Public endpoints are intentionally limited to health/auth bootstrap paths so new
    installs can initialize the first admin without a pre-existing session cookie.
    """

    _PUBLIC_API_PATHS = {
        "/api/health",
        "/api/auth/status",
        "/api/auth/setup",
        "/api/auth/login",
    }

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api") or request.url.path in self._PUBLIC_API_PATHS:
            return await call_next(request)

        store = get_auth_store()
        if not store.has_admin():
            return JSONResponse(
                status_code=403,
                content={"detail": "Admin setup required before accessing protected APIs."},
            )

        parsed = parse_session_cookie(request.cookies.get(SESSION_COOKIE_NAME))
        if not parsed:
            return JSONResponse(status_code=401, content={"detail": "Authentication required."})
        session_id, token_secret = parsed
        token_hash = hash_session_token(token_secret)
        admin = store.validate_session(session_id, token_hash)
        if not admin:
            return JSONResponse(status_code=401, content={"detail": "Authentication required."})
        request.state.admin_id = admin.id
        request.state.admin_username = admin.username
        request.state.authenticated = True
        return await call_next(request)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(app: FastAPI):
    from stackwarden.web.deps import get_catalog, _job_manager  # noqa: F401

    get_catalog()
    _job_manager()
    yield


def create_app(settings: WebSettings | None = None) -> FastAPI:
    settings = settings or WebSettings()
    from stackwarden import __version__
    docs_enabled = bool(settings.dev)
    app = FastAPI(
        title="StackWarden",
        version=__version__,
        lifespan=_lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    # CORS
    if settings.dev:
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Session auth
    app.add_middleware(SessionAuthMiddleware)

    # Global error handler for StackWarden domain errors
    from stackwarden.domain.errors import (
        BlockNotFoundError,
        BuildError,
        CatalogError,
        DriftError,
        IncompatibleStackError,
        ProfileNotFoundError,
        StackNotFoundError,
        StackWardenError,
    )

    @app.exception_handler(ProfileNotFoundError)
    @app.exception_handler(StackNotFoundError)
    @app.exception_handler(BlockNotFoundError)
    async def not_found_handler(request: Request, exc: StackWardenError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(IncompatibleStackError)
    @app.exception_handler(DriftError)
    async def validation_handler(request: Request, exc: StackWardenError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError):
        detail = [
            {
                "field": _format_validation_field(err.get("loc", ())),
                "message": str(err.get("msg", "Invalid value")),
            }
            for err in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.exception_handler(BuildError)
    @app.exception_handler(CatalogError)
    async def build_error_handler(request: Request, exc: StackWardenError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.exception_handler(StackWardenError)
    async def generic_stackwarden_handler(request: Request, exc: StackWardenError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    # Routes
    from stackwarden.web.routes import (
        artifacts,
        blocks,
        catalog,
        compatibility,
        create,
        detection,
        jobs,
        meta,
        plan,
        profiles,
        auth,
        settings as settings_routes,
        stacks,
        system,
        verify,
    )

    app.include_router(profiles.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(stacks.router, prefix="/api")
    app.include_router(blocks.router, prefix="/api")
    app.include_router(artifacts.router, prefix="/api")
    app.include_router(catalog.router, prefix="/api")
    app.include_router(compatibility.router, prefix="/api")
    app.include_router(plan.router, prefix="/api")
    app.include_router(verify.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(system.router, prefix="/api")
    app.include_router(settings_routes.router, prefix="/api")
    app.include_router(detection.router, prefix="/api")
    app.include_router(create.router, prefix="/api")
    app.include_router(meta.router, prefix="/api")

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    # SPA static serving (production): serve built files, fallback to index.html
    if _STATIC_DIR.is_dir():
        @app.get("/{path:path}")
        async def spa_catch_all(path: str):
            file_path = _STATIC_DIR / path
            if file_path.is_file() and file_path.resolve().is_relative_to(_STATIC_DIR.resolve()):
                return FileResponse(file_path)
            index = _STATIC_DIR / "index.html"
            if index.exists():
                return FileResponse(index)
            return JSONResponse(status_code=404, content={"detail": "Not found"})

    return app


app = create_app()


def main() -> None:
    settings = WebSettings()
    uvicorn.run(
        "stackwarden.web.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.dev,
    )


if __name__ == "__main__":
    main()
