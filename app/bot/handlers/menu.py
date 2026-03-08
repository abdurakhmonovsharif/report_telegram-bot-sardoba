from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot.handlers.common import ensure_user
from app.bot.i18n import t
from app.bot.keyboards import branch_keyboard
from app.bot.keyboards import language_keyboard
from app.bot.states import ArrivalStates, TransferStates
from app.config import Settings
from app.db.database import Database

router = Router(name="menu")


@router.callback_query(F.data == "menu:arrival")
async def start_arrival_flow(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    user = await ensure_user(db, callback.from_user)
    lang = user.get("language")

    if not lang:
        if callback.message:
            await callback.message.answer(t("choose_language", "uz"), reply_markup=language_keyboard())
        await callback.answer()
        return

    await state.clear()
    await state.set_state(ArrivalStates.selecting_branch)
    await state.update_data(operation_type="arrival")

    if callback.message:
        await callback.message.answer(
            t("select_branch", lang),
            reply_markup=branch_keyboard(settings.branches, "arrival:branch"),
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

    if not lang:
        if callback.message:
            await callback.message.answer(t("choose_language", "uz"), reply_markup=language_keyboard())
        await callback.answer()
        return

    await state.clear()
    await state.set_state(TransferStates.selecting_branch)
    await state.update_data(operation_type="transfer")

    if callback.message:
        await callback.message.answer(
            t("select_branch", lang),
            reply_markup=branch_keyboard(settings.branches, "transfer:branch"),
        )
    await callback.answer()
