from __future__ import annotations

from typing import Any

import jwt

from app.api.errors import APIError
from app.config import Settings
from app.core.security import (
    ValidationError,
    create_access_token,
    decode_access_token,
    hash_password,
    validate_admin_login,
    validate_admin_password,
    verify_password,
)
from app.db.database import Database


class AuthService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def authenticate(self, *, login: str, password: str) -> dict[str, Any]:
        admin = await self.db.get_admin_by_login(login.strip())
        if not admin or not admin["is_active"]:
            raise APIError(status_code=401, code="unauthorized", message="Неверный логин или пароль.")
        if not verify_password(password, admin["password_hash"]):
            raise APIError(status_code=401, code="unauthorized", message="Неверный логин или пароль.")

        await self.db.update_admin_last_login(int(admin["id"]))
        refreshed_admin = await self.db.get_admin_by_id(int(admin["id"]))
        if refreshed_admin is None:
            raise APIError(status_code=401, code="unauthorized", message="Администратор не найден.")

        await self.db.log_audit(
            actor_type="admin",
            actor_admin_id=int(refreshed_admin["id"]),
            action_type="admin_login",
            entity_type="admin_user",
            entity_id=int(refreshed_admin["id"]),
            message="Администратор выполнил вход в систему.",
        )

        access_token = create_access_token(
            admin_id=int(refreshed_admin["id"]),
            login=str(refreshed_admin["login"]),
            settings=self.settings,
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "admin": self.serialize_admin(refreshed_admin),
        }

    async def get_admin_from_token(self, token: str) -> dict[str, Any]:
        try:
            payload = decode_access_token(token, self.settings)
        except jwt.PyJWTError as exc:
            raise APIError(status_code=401, code="unauthorized", message="Сессия недействительна.") from exc

        admin_id = int(payload["sub"])
        admin = await self.db.get_admin_by_id(admin_id)
        if not admin or not admin["is_active"]:
            raise APIError(status_code=401, code="unauthorized", message="Сессия недействительна.")
        return admin

    async def change_login(
        self,
        *,
        admin_id: int,
        current_password: str,
        new_login: str,
    ) -> dict[str, Any]:
        admin = await self.db.get_admin_by_id(admin_id)
        if not admin:
            raise APIError(status_code=404, code="admin_not_found", message="Администратор не найден.")
        if not verify_password(current_password, admin["password_hash"]):
            raise APIError(status_code=400, code="invalid_password", message="Текущий пароль указан неверно.")

        try:
            validated_login = validate_admin_login(new_login)
        except ValidationError as exc:
            raise APIError(status_code=400, code="invalid_login", message=str(exc)) from exc

        same_login_owner = await self.db.get_admin_by_login(validated_login)
        if same_login_owner and int(same_login_owner["id"]) != admin_id:
            raise APIError(status_code=409, code="login_exists", message="Такой логин уже используется.")

        updated = await self.db.update_admin_login(admin_id=admin_id, login=validated_login)
        if updated is None:
            raise APIError(status_code=500, code="update_failed", message="Не удалось обновить логин.")

        await self.db.log_audit(
            actor_type="admin",
            actor_admin_id=admin_id,
            action_type="admin_profile_login_changed",
            entity_type="admin_user",
            entity_id=admin_id,
            message="Администратор изменил логин профиля.",
            meta={"login": validated_login},
        )
        return self.serialize_admin(updated)

    async def change_password(
        self,
        *,
        admin_id: int,
        current_password: str,
        new_password: str,
    ) -> dict[str, Any]:
        admin = await self.db.get_admin_by_id(admin_id)
        if not admin:
            raise APIError(status_code=404, code="admin_not_found", message="Администратор не найден.")
        if not verify_password(current_password, admin["password_hash"]):
            raise APIError(status_code=400, code="invalid_password", message="Текущий пароль указан неверно.")

        try:
            validated_password = validate_admin_password(new_password)
        except ValidationError as exc:
            raise APIError(status_code=400, code="invalid_password", message=str(exc)) from exc

        updated = await self.db.update_admin_password_hash(
            admin_id=admin_id,
            password_hash=hash_password(validated_password),
        )
        if updated is None:
            raise APIError(status_code=500, code="update_failed", message="Не удалось обновить пароль.")

        await self.db.log_audit(
            actor_type="admin",
            actor_admin_id=admin_id,
            action_type="admin_profile_password_changed",
            entity_type="admin_user",
            entity_id=admin_id,
            message="Администратор изменил пароль профиля.",
        )
        return self.serialize_admin(updated)

    @staticmethod
    def serialize_admin(admin: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": admin["id"],
            "login": admin["login"],
            "full_name": admin["full_name"],
            "is_active": admin["is_active"],
            "last_login_at": admin["last_login_at"],
            "created_at": admin["created_at"],
            "updated_at": admin["updated_at"],
        }
