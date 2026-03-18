from __future__ import annotations

from datetime import date, datetime

from aiogram.types import CallbackQuery, User

from app.bot.i18n import SUPPORTED_LANGUAGES
from app.db.database import Database


async def ensure_user(db: Database, tg_user: User) -> dict:
    name = tg_user.full_name or tg_user.username or str(tg_user.id)
    return await db.upsert_user(
        tg_user.id,
        name,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
        username=tg_user.username,
    )


async def get_user_language(db: Database, tg_user: User, fallback: str = "uz") -> str:
    user = await ensure_user(db, tg_user)
    lang = user.get("language")
    if isinstance(lang, str) and lang in SUPPORTED_LANGUAGES:
        return lang
    return fallback


def parse_iso_date(value: str) -> date | None:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


async def clear_inline_keyboard(callback: CallbackQuery) -> None:
    if callback.message is None:
        return

    try:
        await callback.message.delete()
    except Exception:
        return
