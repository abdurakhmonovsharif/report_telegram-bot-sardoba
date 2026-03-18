from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_admin, get_db, get_settings
from app.api.responses import ok
from app.api.schemas import ChangeLoginRequest, ChangePasswordRequest, LoginRequest
from app.config import Settings
from app.db.database import Database
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
async def login(
    payload: LoginRequest,
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    auth_service = AuthService(db=db, settings=settings)
    return ok(await auth_service.authenticate(login=payload.login, password=payload.password))


@router.get("/me")
async def me(
    admin: dict = Depends(get_current_admin),
) -> dict:
    return ok(AuthService.serialize_admin(admin))


@router.post("/change-login")
async def change_login(
    payload: ChangeLoginRequest,
    admin: dict = Depends(get_current_admin),
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    auth_service = AuthService(db=db, settings=settings)
    return ok(
        await auth_service.change_login(
            admin_id=int(admin["id"]),
            current_password=payload.current_password,
            new_login=payload.new_login,
        )
    )


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    admin: dict = Depends(get_current_admin),
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    auth_service = AuthService(db=db, settings=settings)
    return ok(
        await auth_service.change_password(
            admin_id=int(admin["id"]),
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    )
