from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot.handlers.common import clear_inline_keyboard, ensure_user
from app.bot.i18n import t
from app.bot.keyboards import branch_keyboard, contact_request_keyboard, language_keyboard, main_menu_keyboard, transfer_kind_keyboard
from app.bot.states import ArrivalStates, TransferStates
from app.config import Settings
from app.db.database import Database

router = Router(name="menu")


@router.callback_query(F.data == "nav:main_menu")
async def back_to_main_menu(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
) -> None:
    user = await ensure_user(db, callback.from_user)
    lang = user.get("language") or "uz"

    await state.clear()
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(t("main_menu", lang), reply_markup=main_menu_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data == "menu:arrival")
async def start_arrival_flow(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    user = await ensure_user(db, callback.from_user)
    lang = user.get("language")

    if not user.get("phone_number"):
        if callback.message:
            await callback.message.answer(
                t("phone_request", "uz"),
                reply_markup=contact_request_keyboard(user.get("language") or "uz"),
            )
        await callback.answer()
        return

    if not lang:
        if callback.message:
            await callback.message.answer(t("choose_language", "uz"), reply_markup=language_keyboard())
        await callback.answer()
        return

    branches = await db.list_bot_branches()
    await state.clear()
    await state.set_state(ArrivalStates.selecting_branch)
    await state.update_data(operation_type="arrival")
    await db.log_audit(
        actor_type="telegram_user",
        actor_user_id=user["id"],
        action_type="arrival_flow_started",
        entity_type="request_draft",
        message="Пользователь начал сценарий прихода в Telegram-боте.",
    )

    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(
            t("select_branch", lang),
            reply_markup=branch_keyboard(branches, "arrival:branch", lang=lang, back_callback="nav:main_menu"),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:transfer")
async def start_transfer_flow(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    user = await ensure_user(db, callback.from_user)
    lang = user.get("language")

    if not user.get("phone_number"):
        if callback.message:
            await callback.message.answer(
                t("phone_request", "uz"),
                reply_markup=contact_request_keyboard(user.get("language") or "uz"),
            )
        await callback.answer()
        return

    if not lang:
        if callback.message:
            await callback.message.answer(t("choose_language", "uz"), reply_markup=language_keyboard())
        await callback.answer()
        return

    await state.clear()
    await state.set_state(TransferStates.selecting_transfer_kind)
    await state.update_data(operation_type="transfer")
    await db.log_audit(
        actor_type="telegram_user",
        actor_user_id=user["id"],
        action_type="transfer_flow_started",
        entity_type="request_draft",
        message="Пользователь начал сценарий перемещения в Telegram-боте.",
    )

    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(
            t("select_transfer_kind", lang),
            reply_markup=transfer_kind_keyboard(lang, back_callback="nav:main_menu"),
        )
    await callback.answer()
