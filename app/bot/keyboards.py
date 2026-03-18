from __future__ import annotations

from aiogram.types import (
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.i18n import t


def language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="O'zbek (Default)", callback_data="lang:uz")
    builder.button(text="Русский", callback_data="lang:ru")
    builder.button(text="English", callback_data="lang:en")
    builder.adjust(1)
    return builder.as_markup()


def main_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("arrival", lang), callback_data="menu:arrival")
    builder.button(text=t("transfer", lang), callback_data="menu:transfer")
    builder.button(text=t("change_language", lang), callback_data="menu:language")
    builder.adjust(1)
    return builder.as_markup()


def start_entry_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("start_button", lang))]],
        resize_keyboard=True,
    )


def branch_keyboard(
    branches: list[dict],
    callback_prefix: str,
    *,
    lang: str = "uz",
    back_callback: str | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for branch in branches:
        builder.button(text=branch["bot_name"], callback_data=f"{callback_prefix}:{branch['id']}")
    if back_callback:
        builder.button(text=t("back", lang), callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def warehouse_keyboard(
    warehouses: list[dict],
    callback_prefix: str,
    *,
    lang: str = "uz",
    back_callback: str | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for warehouse in warehouses:
        builder.button(text=warehouse["name"], callback_data=f"{callback_prefix}:{warehouse['id']}")
    if back_callback:
        builder.button(text=t("back", lang), callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def transfer_kind_keyboard(lang: str, *, back_callback: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("transfer_kind_internal", lang), callback_data="transfer:kind:warehouse")
    builder.button(text=t("transfer_kind_branch", lang), callback_data="transfer:kind:branch")
    if back_callback:
        builder.button(text=t("back", lang), callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def arrival_photo_keyboard(lang: str, *, back_callback: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("finish_upload", lang), callback_data="arrival:photos_done")
    builder.button(text=t("arrival_no_photo", lang), callback_data="arrival:no_photo")
    if back_callback:
        builder.button(text=t("back", lang), callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def arrival_items_keyboard(lang: str, *, back_callback: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("arrival_add_more", lang), callback_data="arrival:add_more")
    builder.button(text=t("arrival_continue", lang), callback_data="arrival:items_done")
    if back_callback:
        builder.button(text=t("back", lang), callback_data=back_callback)
    builder.adjust(2, 1)
    return builder.as_markup()


def transfer_photo_keyboard(lang: str, *, back_callback: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("finish_upload", lang), callback_data="transfer:photos_done")
    builder.button(text=t("skip_photos", lang), callback_data="transfer:photos_skip")
    if back_callback:
        builder.button(text=t("back", lang), callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def optional_comment_keyboard(prefix: str, lang: str, *, back_callback: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("skip_optional", lang), callback_data=f"{prefix}:comment_skip")
    if back_callback:
        builder.button(text=t("back", lang), callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def cancel_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("cancel", lang), callback_data="action:cancel")
    return builder.as_markup()


def menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    return main_menu_keyboard(lang)


def contact_request_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("share_phone", lang), request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_reply_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
