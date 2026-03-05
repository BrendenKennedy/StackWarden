"""FastAPI application factory for the Stacksmith Web UI."""

from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from stacksmith.web.settings import WebSettings

log = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"


def _format_validation_field(loc: tuple[object, ...] | list[object]) -> str:
    parts = [str(part) for part in loc if str(part) not in {"body", "query", "path"}]
    return ".".join(parts) if parts else "request"


# ---------------------------------------------------------------------------
# Token auth middleware
# ---------------------------------------------------------------------------

class TokenAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str):
        super().__init__(app)
        self.token = token

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api") and request.url.path != "/api/health":
            auth = request.headers.get("Authorization", "")
            expected = f"Bearer {self.token}"
            if not hmac.compare_digest(auth.encode(), expected.encode()):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing authentication token"},
                )
        return await call_next(request)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(app: FastAPI):
    from stacksmith.web.deps import get_catalog, _job_manager  # noqa: F401

    get_catalog()
    _job_manager()
    yield


def create_app(settings: WebSettings | None = None) -> FastAPI:
    settings = settings or WebSettings()
    from stacksmith import __version__
    docs_enabled = bool(settings.dev)
    app = FastAPI(
        title="Stacksmith",
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

    # Token auth
    if settings.token:
        app.add_middleware(TokenAuthMiddleware, token=settings.token)
    else:
        if settings.dev:
            _no_auth_msg = (
                "WARNING: No STACKSMITH_WEB_TOKEN configured — the web UI is "
                "running WITHOUT AUTHENTICATION. Any network client can trigger "
                "builds and modify the catalog. Set STACKSMITH_WEB_TOKEN to "
                "enable bearer-token auth."
            )
            log.warning(_no_auth_msg)
            import sys
            print(f"\n{'=' * 72}\n{_no_auth_msg}\n{'=' * 72}\n", file=sys.stderr)
        else:
            raise RuntimeError(
                "STACKSMITH_WEB_TOKEN is required when STACKSMITH_WEB_DEV is false."
            )

    # Global error handler for Stacksmith domain errors
    from stacksmith.domain.errors import (
        BlockNotFoundError,
        BuildError,
        CatalogError,
        DriftError,
        IncompatibleStackError,
        ProfileNotFoundError,
        StackNotFoundError,
        StacksmithError,
    )

    @app.exception_handler(ProfileNotFoundError)
    @app.exception_handler(StackNotFoundError)
    @app.exception_handler(BlockNotFoundError)
    async def not_found_handler(request: Request, exc: StacksmithError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(IncompatibleStackError)
    @app.exception_handler(DriftError)
    async def validation_handler(request: Request, exc: StacksmithError):
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
    async def build_error_handler(request: Request, exc: StacksmithError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.exception_handler(StacksmithError)
    async def generic_stacksmith_handler(request: Request, exc: StacksmithError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    # Routes
    from stacksmith.web.routes import (
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
        settings as settings_routes,
        stacks,
        system,
        verify,
    )

    app.include_router(profiles.router, prefix="/api")
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
        "stacksmith.web.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.dev,
    )


if __name__ == "__main__":
    main()
