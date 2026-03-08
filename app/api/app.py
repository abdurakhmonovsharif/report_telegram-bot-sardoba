from __future__ import annotations

import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.admin import router as admin_router
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
        title="Restaurant Warehouse Admin API",
        description="Administration API for requests, users, logs and statistics.",
        version="1.0.0",
        lifespan=lifespan,
    )

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
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )

    @app.get("/health", tags=["health"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(admin_router)
    return app


app = create_api_app()
