from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.common import ensure_user
from app.bot.i18n import SUPPORTED_LANGUAGES, t
from app.bot.keyboards import language_keyboard, main_menu_keyboard
from app.db.database import Database

router = Router(name="start")


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    user = await ensure_user(db, message.from_user)

    if not user.get("language"):
        await message.answer(t("choose_language", "uz"), reply_markup=language_keyboard())
        return

    lang = user["language"]
    await message.answer(t("main_menu", lang), reply_markup=main_menu_keyboard(lang))


@router.message(Command("language"))
async def language_command(message: Message, state: FSMContext, db: Database) -> None:
    await ensure_user(db, message.from_user)
    await state.clear()
    await message.answer(t("choose_language", "uz"), reply_markup=language_keyboard())


@router.callback_query(F.data == "menu:language")
async def language_menu_callback(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    await ensure_user(db, callback.from_user)
    await state.clear()
    if callback.message:
        await callback.message.answer(t("choose_language", "uz"), reply_markup=language_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("lang:"))
async def save_language(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = callback.data.split(":", 1)[1]
    if lang not in SUPPORTED_LANGUAGES:
        await callback.answer("Unsupported language", show_alert=True)
        return

    await ensure_user(db, callback.from_user)
    await db.update_user_language(callback.from_user.id, lang)
    await state.clear()

    await db.log_event(
        level="INFO",
        event_type="language_changed",
        message="User selected language",
        context={"telegram_user_id": callback.from_user.id, "language": lang},
    )

    if callback.message:
        await callback.message.answer(t("language_saved", lang))
        await callback.message.answer(t("main_menu", lang), reply_markup=main_menu_keyboard(lang))
    await callback.answer()


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    user = await ensure_user(db, message.from_user)
    lang = user.get("language")
    if not lang:
        await message.answer(t("choose_language", "uz"), reply_markup=language_keyboard())
        return
    await message.answer(t("cancelled", lang))
    await message.answer(t("main_menu", lang), reply_markup=main_menu_keyboard(lang))


@router.callback_query(F.data == "action:cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.clear()
    user = await ensure_user(db, callback.from_user)
    lang = user.get("language")
    if callback.message:
        if not lang:
            await callback.message.answer(t("choose_language", "uz"), reply_markup=language_keyboard())
            await callback.answer()
            return
        await callback.message.answer(t("cancelled", lang))
        await callback.message.answer(t("main_menu", lang), reply_markup=main_menu_keyboard(lang))
    await callback.answer()


@router.message(StateFilter(None))
async def idle_entrypoint(message: Message, db: Database) -> None:
    user = await ensure_user(db, message.from_user)
    lang = user.get("language")
    if not lang:
        await message.answer(t("choose_language", "uz"), reply_markup=language_keyboard())
        return
    await message.answer(t("main_menu", lang), reply_markup=main_menu_keyboard(lang))
