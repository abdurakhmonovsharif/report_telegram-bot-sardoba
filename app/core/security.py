from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.config import Settings


class ValidationError(ValueError):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def validate_admin_login(login: str) -> str:
    stripped = login.strip()
    if len(stripped) < 8:
        raise ValidationError("Логин должен содержать минимум 8 символов.")
    if not stripped.isalnum():
        raise ValidationError("Логин может содержать только латинские буквы и цифры.")
    if sum(char.isupper() for char in stripped) < 1:
        raise ValidationError("Логин должен содержать минимум одну заглавную букву.")
    if sum(char.islower() for char in stripped) < 5:
        raise ValidationError("Логин должен содержать минимум пять строчных букв.")
    if sum(char.isdigit() for char in stripped) < 2:
        raise ValidationError("Логин должен содержать минимум две цифры.")
    return stripped


def validate_admin_password(password: str) -> str:
    stripped = password.strip()
    if len(stripped) < 8:
        raise ValidationError("Пароль должен содержать минимум 8 символов.")
    if not stripped.isalnum():
        raise ValidationError("Пароль может содержать только латинские буквы и цифры.")
    return stripped


def create_access_token(
    *,
    admin_id: int,
    login: str,
    settings: Settings,
    expires_delta: timedelta | None = None,
) -> str:
    lifetime = expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(admin_id),
        "login": login,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "exp", "type"]},
    )
