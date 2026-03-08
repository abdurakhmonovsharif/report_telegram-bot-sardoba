from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.common import get_user_language
from app.bot.i18n import t
from app.bot.keyboards import main_menu_keyboard, transfer_photo_keyboard, warehouse_keyboard
from app.bot.states import TransferStates
from app.config import Settings
from app.db.database import Database
from app.services.request_service import ReportDeliveryError, RequestService

router = Router(name="transfer")


@router.callback_query(TransferStates.selecting_branch, F.data.startswith("transfer:branch:"))
async def transfer_select_branch(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    lang = await get_user_language(db, callback.from_user)
    branch = callback.data.split(":", 2)[2]

    if branch not in settings.branches:
        await callback.answer(t("use_buttons", lang), show_alert=True)
        return

    warehouses = settings.warehouses_for_branch(branch)
    await state.update_data(branch=branch)
    await state.set_state(TransferStates.selecting_warehouse)

    if callback.message:
        await callback.message.answer(
            t("select_warehouse", lang),
            reply_markup=warehouse_keyboard(warehouses, "transfer:warehouse"),
        )
    await callback.answer()


@router.callback_query(TransferStates.selecting_warehouse, F.data.startswith("transfer:warehouse:"))
async def transfer_select_warehouse(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    lang = await get_user_language(db, callback.from_user)
    warehouse = callback.data.split(":", 2)[2]

    data = await state.get_data()
    branch = data.get("branch")
    if branch is None or warehouse not in settings.warehouses_for_branch(branch):
        await callback.answer(t("use_buttons", lang), show_alert=True)
        return

    await state.update_data(warehouse=warehouse)
    await state.set_state(TransferStates.waiting_comment)

    if callback.message:
        await callback.message.answer(t("comment_prompt", lang))
    await callback.answer()


@router.message(TransferStates.waiting_comment, F.text)
async def transfer_comment(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    comment_text = message.text.strip()

    if not comment_text:
        await message.answer(t("comment_prompt", lang))
        return

    await state.update_data(comment=comment_text, photos=[])
    await state.set_state(TransferStates.collecting_optional_photos)
    await message.answer(
        t("transfer_photo_prompt", lang),
        reply_markup=transfer_photo_keyboard(lang),
    )


@router.message(TransferStates.collecting_optional_photos, F.photo)
async def transfer_collect_photos(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    data = await state.get_data()
    photos = list(data.get("photos", []))
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)

    await message.answer(
        t("arrival_photo_done", lang, count=len(photos)),
        reply_markup=transfer_photo_keyboard(lang),
    )


@router.callback_query(
    TransferStates.collecting_optional_photos,
    F.data.in_({"transfer:photos_done", "transfer:photos_skip"}),
)
async def transfer_finalize(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    request_service: RequestService,
) -> None:
    lang = await get_user_language(db, callback.from_user)
    data = await state.get_data()

    photos = data.get("photos", []) if callback.data == "transfer:photos_done" else []

    try:
        request_record = await request_service.finalize_request(
            telegram_user_id=callback.from_user.id,
            telegram_user_name=callback.from_user.full_name or str(callback.from_user.id),
            operation_type="transfer",
            branch=data["branch"],
            warehouse=data["warehouse"],
            comment=data.get("comment"),
            photos=photos,
        )
    except ReportDeliveryError:
        await state.clear()
        if callback.message:
            await callback.message.answer(t("request_saved_but_not_sent", lang))
            await callback.message.answer(t("main_menu", lang), reply_markup=main_menu_keyboard(lang))
        await callback.answer()
        return
    except Exception:
        if callback.message:
            await callback.message.answer(t("safe_error", lang))
        await callback.answer()
        return

    await state.clear()
    if callback.message:
        await callback.message.answer(t("request_success", lang, request_id=request_record["id"]))
        await callback.message.answer(t("main_menu", lang), reply_markup=main_menu_keyboard(lang))
    await callback.answer()


@router.message(TransferStates.selecting_branch)
@router.message(TransferStates.selecting_warehouse)
async def transfer_buttons_only(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("use_buttons", lang))


@router.message(TransferStates.waiting_comment)
async def transfer_comment_only(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("comment_prompt", lang))


@router.message(TransferStates.collecting_optional_photos)
async def transfer_photo_or_buttons(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("transfer_photo_prompt", lang))
