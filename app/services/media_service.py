from __future__ import annotations

from io import BytesIO
from typing import Any

from aiogram import Bot

from app.api.errors import APIError
from app.config import Settings
from app.db.database import Database


class MediaService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def _download_file_bytes(self, file_id: str) -> bytes:
        bot = Bot(token=self.settings.bot_token)
        try:
            telegram_file = await bot.get_file(file_id)
            buffer = BytesIO()
            await bot.download_file(telegram_file.file_path, destination=buffer)
            return buffer.getvalue()
        finally:
            await bot.session.close()

    async def get_operation_photo(self, photo_id: int) -> dict[str, Any]:
        photo = await self.db.get_request_photo_by_id(photo_id)
        if photo is None:
            raise APIError(status_code=404, code="media_not_found", message="Изображение не найдено.")
        payload = await self._download_file_bytes(str(photo["telegram_file_id"]))
        return {
            "filename": f"{photo['operation_code'] or photo_id}.jpg",
            "content_type": "image/jpeg",
            "content": payload,
            "meta": photo,
        }

    async def get_user_avatar(self, user_id: int) -> dict[str, Any]:
        user = await self.db.fetchrow(
            """
            SELECT id, name, avatar_file_id, avatar_width, avatar_height, avatar_file_size
            FROM users
            WHERE id = $1
            """,
            user_id,
        )
        if user is None or not user.get("avatar_file_id"):
            raise APIError(status_code=404, code="avatar_not_found", message="Аватар не найден.")
        payload = await self._download_file_bytes(str(user["avatar_file_id"]))
        return {
            "filename": f"user-{user_id}-avatar.jpg",
            "content_type": "image/jpeg",
            "content": payload,
            "meta": user,
        }
