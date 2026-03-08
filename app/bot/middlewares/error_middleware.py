from __future__ import annotations

import traceback
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.db.database import Database


SAFE_ERROR_TEXT = (
    "Server error occurred. Please try again later.\n"
    "Serverda xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.\n"
    "Произошла серверная ошибка. Попробуйте позже."
)


class ErrorLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception:
            db: Database | None = data.get("db")
            stack_trace = traceback.format_exc()
            context: dict[str, Any] = {
                "event_type": type(event).__name__,
            }

            user = getattr(event, "from_user", None)
            if user is not None:
                context["telegram_user_id"] = user.id

            if db is not None:
                try:
                    await db.log_event(
                        level="ERROR",
                        event_type="bot_handler_exception",
                        message="Unhandled exception in bot handler",
                        context=context,
                        stack_trace=stack_trace,
                    )
                except Exception:
                    pass

            await self._safe_reply(event)
            return None

    async def _safe_reply(self, event: TelegramObject) -> None:
        try:
            if isinstance(event, Message):
                await event.answer(SAFE_ERROR_TEXT)
                return

            if isinstance(event, CallbackQuery):
                await event.answer("Server error", show_alert=True)
                if event.message is not None:
                    await event.message.answer(SAFE_ERROR_TEXT)
        except Exception:
            return
