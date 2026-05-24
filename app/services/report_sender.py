from __future__ import annotations

import json
from html import escape
from datetime import date as DateType
from datetime import datetime
from typing import Any, Mapping

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InputMediaPhoto

from app.config import Settings
from app.core.numeric import format_numeric_value, is_valid_numeric_value
from app.db.database import Database


OPERATION_LABELS = {
    "arrival": "Prixod",
    "act_razbora": "Акт разбора",
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
        if request_record.get("operation_type") == "act_razbora":
            group_binding = await self.db.get_operation_group_binding("act_razbora")
            target_group_id = (
                int(group_binding["group_chat_id"])
                if group_binding and group_binding.get("group_chat_id") is not None
                else self.settings.default_report_chat_id
            )
            if target_group_id is None:
                raise ValueError("No Telegram group mapping for act_razbora reports")

            file_ids = self._extract_file_ids(photos)
            caption = self._build_caption(request_record, user_record, photos_count=len(file_ids))
            try:
                await self._send_report_payload(target_group_id=target_group_id, file_ids=file_ids, caption=caption)
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
            return

        warehouse = request_record["warehouse"]
        warehouse_slug: str | None = None
        warehouse_group_chat_id: int | None = None
        target_warehouse_id = request_record.get("warehouse_id")

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
            await self._send_report_payload(target_group_id=target_group_id, file_ids=file_ids, caption=caption)
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

    async def _send_report_payload(self, *, target_group_id: int, file_ids: list[str], caption: str) -> None:
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
        if request_record.get("operation_type") == "act_razbora":
            return self._build_act_razbora_caption(
                request_record=request_record,
                user_record=user_record,
            )

        display_date = self._format_display_date(request_record)
        line_items = self._extract_line_items(request_record)

        lines = [
            self._format_operation_header("arrival"),
            "",
            self._format_detail_line("📆", "Дата", display_date),
            self._format_detail_line("📍", "Филиал", request_record.get("branch")),
            self._format_detail_line("♻️", "На склад", request_record.get("warehouse")),
        ]

        if request_record.get("supplier_name"):
            lines.append(self._format_detail_line("🚚", "Поставщик", request_record["supplier_name"]))

        lines.append("")

        if line_items:
            lines.append("⚠️ <b>Номенклатура:</b>")
            lines.extend(self._format_line_item(item) for item in line_items)
        else:
            lines.append(
                self._format_detail_line("⚠️", "Номенклатура", self._format_nomenclature(request_record))
            )

        if request_record.get("comment"):
            lines.append("")
            lines.append(self._format_detail_line("💬", "Комментарий", request_record["comment"]))

        if request_record.get("info_text"):
            if not request_record.get("comment"):
                lines.append("")
            lines.append(self._format_detail_line("ℹ️", "Доп. инфо", request_record["info_text"]))

        lines.extend(
            [
                "",
                self._format_detail_line("👤", "Отправитель", user_record.get("name")),
                self._format_detail_line("📞", "Телефон", user_record.get("phone_number")),
                self._format_detail_line("📷", "Фото", self._format_photos_status(photos_count)),
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _format_display_date(request_record: Mapping[str, Any]) -> str:
        document_date = request_record.get("date")
        if isinstance(document_date, datetime):
            return document_date.strftime("%d/%m/%Y")
        if isinstance(document_date, DateType):
            return document_date.strftime("%d/%m/%Y")
        created_at = request_record.get("created_at")
        if isinstance(created_at, datetime):
            return created_at.strftime("%d/%m/%Y")
        return datetime.utcnow().strftime("%d/%m/%Y")

    @staticmethod
    def _format_nomenclature(request_record: Mapping[str, Any]) -> str:
        line_items = ReportSender._extract_line_items(request_record)
        if line_items:
            return " + ".join(ReportSender._format_line_item(item) for item in line_items)
        nomenclature_parts = [
            ReportSender._format_numeric_display(value, fallback=ReportSender._normalize_display_value(value))
            if key == "quantity"
            else ReportSender._normalize_display_value(value)
            for key, value in (
                ("product_name", request_record.get("product_name")),
                ("quantity", request_record.get("quantity")),
            )
            if value and ReportSender._normalize_display_value(value)
        ]
        return " + ".join(nomenclature_parts) or "Нет данных"

    @staticmethod
    def _extract_line_items(request_record: Mapping[str, Any]) -> list[dict[str, str]]:
        raw_items = request_record.get("line_items") or []
        if isinstance(raw_items, str):
            try:
                raw_items = json.loads(raw_items)
            except json.JSONDecodeError:
                raw_items = []

        if not isinstance(raw_items, list):
            return []

        line_items: list[dict[str, str]] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, Mapping):
                continue

            product_name = str(raw_item.get("product_name") or "").strip()
            quantity = ReportSender._format_numeric_display(raw_item.get("quantity"))
            unit_price = ReportSender._format_numeric_display(raw_item.get("unit_price"))
            if not product_name or not quantity:
                continue

            line_item = {
                "product_name": product_name,
                "quantity": quantity,
            }
            if unit_price:
                line_item["unit_price"] = unit_price
            line_items.append(line_item)
        return line_items

    @staticmethod
    def _format_line_item(line_item: Mapping[str, Any]) -> str:
        product_name = escape(str(line_item.get("product_name") or "").strip() or "Нет данных")
        quantity = escape(ReportSender._format_numeric_display(line_item.get("quantity"), fallback="Нет данных"))
        unit_price = escape(ReportSender._format_numeric_display(line_item.get("unit_price")))
        if unit_price:
            return f"• {product_name} — {quantity} × {unit_price}"
        return f"• {product_name} — {quantity}"

    @staticmethod
    def _format_kg_line_item(line_item: Mapping[str, Any]) -> str:
        product_name = escape(str(line_item.get("product_name") or "").strip() or "Нет данных")
        quantity = escape(ReportSender._format_numeric_display(line_item.get("quantity"), fallback="Нет данных"))
        return f"• {product_name} — {quantity} kg"

    @staticmethod
    def _format_operation_header(operation_type: str) -> str:
        icon = "📦" if operation_type == "arrival" else "🧾"
        label = OPERATION_LABELS.get(operation_type, "Операция")
        return f"{icon} <b>{escape(label)}</b>"

    @staticmethod
    def _format_detail_line(icon: str, label: str, value: Any) -> str:
        normalized_value = str(value).strip() if value is not None else ""
        if not normalized_value:
            normalized_value = "Нет данных"
        return f"{icon} <b>{escape(label)}:</b> {escape(normalized_value)}"

    @staticmethod
    def _format_photos_status(photos_count: int) -> str:
        if photos_count <= 0:
            return "нет"
        if photos_count == 1:
            return "1 шт."
        return f"{photos_count} шт."

    @staticmethod
    def _normalize_display_value(value: Any) -> str:
        return str(value).strip() if value is not None else ""

    @staticmethod
    def _format_numeric_display(value: Any, *, fallback: str = "") -> str:
        normalized = ReportSender._normalize_display_value(value)
        if not normalized:
            return fallback
        if is_valid_numeric_value(normalized):
            return format_numeric_value(normalized)
        return normalized

    def _build_act_razbora_caption(
        self,
        *,
        request_record: dict,
        user_record: dict,
    ) -> str:
        display_date = self._format_display_date(request_record)
        line_items = self._extract_line_items(request_record)

        lines = [
            self._format_operation_header("act_razbora"),
            "",
            self._format_detail_line("📆", "Дата", display_date),
            self._format_detail_line("📍", "Филиал", request_record.get("branch")),
            "",
            self._format_detail_line("🥩", "Маҳсулот", request_record.get("product_name")),
            self._format_detail_line(
                "⚖️",
                "Жами кг",
                f"{self._format_numeric_display(request_record.get('quantity'), fallback='Нет данных')} kg",
            ),
            "",
            "⚠️ <b>Номенклатура:</b>",
        ]

        if line_items:
            lines.extend(self._format_kg_line_item(item) for item in line_items)
        else:
            lines.append("Нет данных")

        lines.extend(
            [
                "",
                self._format_detail_line("👤", "Отправитель", user_record.get("name")),
                self._format_detail_line("📞", "Телефон", user_record.get("phone_number")),
            ]
        )
        return "\n".join(lines)
