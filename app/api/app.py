from __future__ import annotations

import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.errors import APIError
from app.api.responses import error_response
from app.api.routes import (
    analytics_router,
    audit_router,
    auth_router,
    catalog_router,
    dashboard_router,
    media_router,
    operations_router,
    users_router,
)
from app.config import Settings, get_settings
from app.db.database import Database


def create_api_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(app_settings)
        await db.connect()
        app.state.db = db
        app.state.settings = app_settings

        try:
            await db.log_event(
                level="INFO",
                event_type="api_startup",
                message="Admin API started",
            )
        except Exception:
            pass
        try:
            yield
        finally:
            try:
                await db.log_event(
                    level="INFO",
                    event_type="api_shutdown",
                    message="Admin API stopped",
                )
            except Exception:
                pass
            await db.disconnect()

    app = FastAPI(
        title="Warehouse Admin Platform API",
        description="Полноценный API для Telegram-бота склада и русскоязычной административной панели.",
        version="2.0.0",
        lifespan=lifespan,
    )

    origins = [origin.strip() for origin in app_settings.frontend_origin.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(APIError)
    async def api_error_handler(_: Request, exc: APIError) -> JSONResponse:
        status_code, payload = error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )
        return JSONResponse(status_code=status_code, content=payload)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        status_code, payload = error_response(
            status_code=exc.status_code,
            code="http_error",
            message=str(exc.detail),
        )
        return JSONResponse(status_code=status_code, content=payload)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        status_code, payload = error_response(
            status_code=422,
            code="validation_error",
            message="Ошибка валидации входных данных.",
            details=exc.errors(),
        )
        return JSONResponse(status_code=status_code, content=payload)

    @app.middleware("http")
    async def log_exceptions(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            db: Database = request.app.state.db
            await db.log_event(
                level="ERROR",
                event_type="api_exception",
                message="Unhandled exception in API",
                context={"path": str(request.url.path), "method": request.method},
                stack_trace=traceback.format_exc(),
            )
            status_code, payload = error_response(
                status_code=500,
                code="internal_server_error",
                message="Ошибка сервера. Попробуйте снова.",
            )
            return JSONResponse(status_code=status_code, content=payload)

    @app.get("/health", tags=["health"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(users_router)
    app.include_router(operations_router)
    app.include_router(catalog_router)
    app.include_router(analytics_router)
    app.include_router(audit_router)
    app.include_router(media_router)

    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    frontend_assets = frontend_dist / "assets"
    frontend_index = frontend_dist / "index.html"

    if frontend_assets.exists():
        app.mount("/panel/assets", StaticFiles(directory=frontend_assets), name="panel-assets")

    if frontend_index.exists():
        @app.get("/", include_in_schema=False)
        async def serve_frontend_root() -> FileResponse:
            return FileResponse(frontend_index)

        @app.get("/panel", include_in_schema=False)
        async def serve_frontend_panel() -> FileResponse:
            return FileResponse(frontend_index)

        @app.get("/panel/{full_path:path}", include_in_schema=False)
        async def serve_frontend(full_path: str) -> FileResponse:
            target = frontend_dist / full_path
            if target.exists() and target.is_file():
                return FileResponse(target)
            return FileResponse(frontend_index)

    return app


app = create_api_app()
