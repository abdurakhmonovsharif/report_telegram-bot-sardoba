from __future__ import annotations

from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InputMediaPhoto

from app.config import Settings
from app.db.database import Database


OPERATION_LABELS = {
    "arrival": "Приход",
    "transfer": "Перемещение",
}


class ReportSender:
    def __init__(self, bot: Bot, settings: Settings, db: Database) -> None:
        self.bot = bot
        self.settings = settings
        self.db = db

    async def send_request_report(
        self,
        *,
        request_record: dict,
        photos: list[str],
        user_record: dict,
    ) -> None:
        branch = request_record["branch"]
        warehouse = request_record["warehouse"]

        target_group_id = self.settings.group_for(branch, warehouse)
        if target_group_id is None:
            raise ValueError(
                f"No Telegram group mapping for branch='{branch}', warehouse='{warehouse}'"
            )

        caption = self._build_caption(request_record, user_record)

        try:
            if photos:
                remaining = list(photos)
                first_batch = True

                while remaining:
                    chunk = remaining[:10]
                    remaining = remaining[10:]

                    if len(chunk) == 1:
                        await self.bot.send_photo(
                            chat_id=target_group_id,
                            photo=chunk[0],
                            caption=caption if first_batch else None,
                        )
                    else:
                        media = [
                            InputMediaPhoto(
                                media=file_id,
                                caption=caption if first_batch and index == 0 else None,
                            )
                            for index, file_id in enumerate(chunk)
                        ]
                        await self.bot.send_media_group(chat_id=target_group_id, media=media)
                    first_batch = False
            else:
                await self.bot.send_message(chat_id=target_group_id, text=caption)
        except TelegramAPIError as exc:
            await self.db.log_event(
                level="ERROR",
                event_type="telegram_api_error",
                message="Telegram API error while sending report",
                context={
                    "request_id": request_record["id"],
                    "target_group_id": target_group_id,
                    "error": str(exc),
                },
            )
            raise

    def _build_caption(self, request_record: dict, user_record: dict) -> str:
        created_at = request_record.get("created_at")
        if isinstance(created_at, datetime):
            ts = created_at.strftime("%Y-%m-%d %H:%M:%S")
        else:
            ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            "Складской отчет",
            f"Тип операции: {OPERATION_LABELS.get(request_record['operation_type'], request_record['operation_type'])}",
            f"Филиал: {request_record['branch']}",
            f"Склад: {request_record['warehouse']}",
        ]

        if request_record.get("supplier_name"):
            lines.append(f"Поставщик: {request_record['supplier_name']}")

        if request_record.get("date"):
            lines.append(f"Сана: {request_record['date']}")

        if request_record.get("comment"):
            lines.append(f"Изох: {request_record['comment']}")

        lines.extend(
            [
                f"Отправитель: {user_record['name']}",
                f"Время: {ts}",
                f"ID заявки: {request_record['id']}",
            ]
        )
        return "\n".join(lines)
