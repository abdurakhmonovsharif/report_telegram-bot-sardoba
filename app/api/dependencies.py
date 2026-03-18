from __future__ import annotations

from typing import Any

from fastapi import Header, HTTPException, Request, status

from app.api.errors import APIError
from app.config import Settings
from app.db.database import Database
from app.services.auth_service import AuthService


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


async def get_current_admin(
    request: Request,
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    db: Database = request.app.state.db
    settings: Settings = request.app.state.settings

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        auth_service = AuthService(db=db, settings=settings)
        return await auth_service.get_admin_from_token(token)

    if settings.admin_token and x_admin_token == settings.admin_token:
        admin = await db.fetchrow(
            """
            SELECT id, login, password_hash, full_name, is_active, last_login_at, created_at, updated_at
            FROM admin_users
            WHERE is_active = TRUE
            ORDER BY id
            LIMIT 1
            """
        )
        if admin:
            return admin

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Доступ запрещен.",
    )


async def require_admin(request: Request) -> dict[str, Any]:
    try:
        return await get_current_admin(request)
    except APIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
