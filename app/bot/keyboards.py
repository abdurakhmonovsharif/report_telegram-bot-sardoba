from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
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


def branch_keyboard(branches: list[str], callback_prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for branch in branches:
        builder.button(text=branch, callback_data=f"{callback_prefix}:{branch}")
    builder.adjust(1)
    return builder.as_markup()


def warehouse_keyboard(warehouses: list[str], callback_prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for warehouse in warehouses:
        builder.button(text=warehouse, callback_data=f"{callback_prefix}:{warehouse}")
    builder.adjust(1)
    return builder.as_markup()


def arrival_photo_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("finish_upload", lang), callback_data="arrival:photos_done")
    builder.button(text=t("arrival_no_photo", lang), callback_data="arrival:no_photo")
    builder.adjust(1)
    return builder.as_markup()


def transfer_photo_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("finish_upload", lang), callback_data="transfer:photos_done")
    builder.button(text=t("skip_photos", lang), callback_data="transfer:photos_skip")
    builder.adjust(1)
    return builder.as_markup()


def cancel_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("cancel", lang), callback_data="action:cancel")
    return builder.as_markup()


def menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    return main_menu_keyboard(lang)
