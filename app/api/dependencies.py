from __future__ import annotations

from fastapi import Header, HTTPException, Request, status

from app.config import Settings
from app.db.database import Database


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def verify_admin_token(
    request: Request,
    x_admin_token: str | None = Header(default=None),
) -> None:
    settings: Settings = request.app.state.settings
    if not settings.admin_token:
        return

    if x_admin_token != settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )
