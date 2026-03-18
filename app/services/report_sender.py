from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

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
        photos: list[str | Mapping[str, Any]],
        user_record: dict,
    ) -> None:
        branch = request_record["branch"]
        warehouse = request_record["warehouse"]
        warehouse_slug: str | None = None
        warehouse_group_chat_id: int | None = None
        target_warehouse_id = request_record.get("to_warehouse_id") or request_record.get("warehouse_id")
        transfer_type = request_record.get("transfer_type") or request_record.get("transfer_kind")

        if target_warehouse_id:
            warehouse_record = await self.db.get_warehouse_by_id(int(target_warehouse_id))
            if warehouse_record:
                warehouse_slug = warehouse_record.get("slug")
                warehouse_group_chat_id = warehouse_record.get("group_chat_id")
                warehouse = warehouse_record.get("name") or warehouse
        elif warehouse:
            warehouse_record = await self.db.get_active_warehouse_by_name(str(warehouse))
            if warehouse_record:
                warehouse_slug = warehouse_record.get("slug")
                warehouse_group_chat_id = warehouse_record.get("group_chat_id")

        if transfer_type == "branch" and warehouse_group_chat_id is None and warehouse_slug is None:
            target_group_id = self.settings.default_report_chat_id
        else:
            target_group_id = warehouse_group_chat_id or self.settings.group_for_warehouse(
                warehouse_slug=warehouse_slug,
                warehouse_name=warehouse,
            )
        if target_group_id is None and warehouse:
            target_group_id = self.settings.group_for(branch, warehouse)
        if target_group_id is None:
            raise ValueError(
                f"No Telegram group mapping for branch='{branch}', warehouse='{warehouse}'"
            )

        file_ids = self._extract_file_ids(photos)
        caption = self._build_caption(request_record, user_record, photos_count=len(file_ids))

        try:
            if file_ids:
                remaining = list(file_ids)
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

    @staticmethod
    def _extract_file_ids(photos: list[str | Mapping[str, Any]]) -> list[str]:
        file_ids: list[str] = []
        for photo in photos:
            if isinstance(photo, str):
                file_ids.append(photo)
                continue

            telegram_file_id = photo.get("telegram_file_id")
            if telegram_file_id:
                file_ids.append(str(telegram_file_id))
        return file_ids

    def _build_caption(self, request_record: dict, user_record: dict, *, photos_count: int) -> str:
        if request_record.get("operation_type") == "transfer":
            return self._build_transfer_caption(request_record=request_record, user_record=user_record)

        display_date = self._format_display_date(request_record)
        nomenclature = self._format_nomenclature(request_record)

        lines = [
            f"📆дата: {display_date}",
            f"📍филиал: {request_record.get('branch') or 'Нет данных'}",
            f"♻️на склад: {request_record.get('warehouse') or 'Нет данных'}",
            f"⚠️номенклатура: {nomenclature}",
        ]

        if request_record.get("supplier_name"):
            lines.append(f"🚚поставщик: {request_record['supplier_name']}")

        if request_record.get("comment"):
            lines.append(f"💬комментарий: {request_record['comment']}")

        if request_record.get("info_text"):
            lines.append(f"ℹ️доп. инфо: {request_record['info_text']}")

        lines.extend([
            f"👤отправитель: {user_record['name']}",
            f"📞телефон: {user_record.get('phone_number') or 'Нет данных'}",
            "📷фото:",
        ])
        return "\n".join(lines)

    @staticmethod
    def _format_display_date(request_record: Mapping[str, Any]) -> str:
        created_at = request_record.get("created_at")
        if isinstance(created_at, datetime):
            return created_at.strftime("%d/%m/%Y")
        return datetime.utcnow().strftime("%d/%m/%Y")

    @staticmethod
    def _format_nomenclature(request_record: Mapping[str, Any]) -> str:
        nomenclature_parts = [
            str(value).strip()
            for value in (request_record.get("product_name"), request_record.get("quantity"))
            if value and str(value).strip()
        ]
        return " + ".join(nomenclature_parts) or "Нет данных"

    def _build_transfer_caption(
        self,
        *,
        request_record: dict,
        user_record: dict,
    ) -> str:
        display_date = self._format_display_date(request_record)
        nomenclature = self._format_nomenclature(request_record)
        transfer_type = request_record.get("transfer_type") or request_record.get("transfer_kind")
        destination_branch = request_record.get("branch") or "Нет данных"
        destination_warehouse = request_record.get("warehouse") or "Нет данных"
        source_branch = request_record.get("source_branch") or request_record.get("from_branch_name")
        source_warehouse = request_record.get("source_warehouse") or request_record.get("from_warehouse_name")

        if transfer_type == "warehouse":
            lines = [
                f"📆дата: {display_date}",
                f"📍филиал: {destination_branch}",
                f"♻️со склада: {source_warehouse or 'Нет данных'}",
                f"♻️на склад: {destination_warehouse}",
                f"⚠️номенклатура: {nomenclature}",
            ]
        elif transfer_type == "branch":
            lines = [
                f"📆дата: {display_date}",
                f"📍филиал получатель: {destination_branch}",
                f"📍филиал отправитель: {source_branch or 'Нет данных'}",
                f"⚠️номенклатура: {nomenclature}",
            ]
        else:
            lines = [
                f"📆дата: {display_date}",
                f"📍филиал: {destination_branch}",
                f"♻️на склад: {destination_warehouse}",
                f"⚠️номенклатура: {nomenclature}",
            ]

        if request_record.get("comment"):
            lines.append(f"💬комментарий: {request_record['comment']}")
        if request_record.get("info_text"):
            lines.append(f"ℹ️доп. инфо: {request_record['info_text']}")

        lines.extend([
            f"👤отправитель: {user_record['name']}",
            f"📞телефон: {user_record.get('phone_number') or 'Нет данных'}",
            "📷фото:",
        ])
        return "\n".join(lines)
