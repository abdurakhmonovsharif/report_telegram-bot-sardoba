from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.common import get_user_language, parse_iso_date
from app.bot.i18n import t
from app.bot.keyboards import arrival_photo_keyboard, main_menu_keyboard, warehouse_keyboard
from app.bot.states import ArrivalStates
from app.config import Settings
from app.db.database import Database
from app.services.request_service import ReportDeliveryError, RequestService

router = Router(name="arrival")


@router.callback_query(ArrivalStates.selecting_branch, F.data.startswith("arrival:branch:"))
async def arrival_select_branch(
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
    await state.set_state(ArrivalStates.selecting_warehouse)

    if callback.message:
        await callback.message.answer(
            t("select_warehouse", lang),
            reply_markup=warehouse_keyboard(warehouses, "arrival:warehouse"),
        )
    await callback.answer()


@router.callback_query(ArrivalStates.selecting_warehouse, F.data.startswith("arrival:warehouse:"))
async def arrival_select_warehouse(
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

    await state.update_data(warehouse=warehouse, photos=[], no_invoice=False)
    await state.set_state(ArrivalStates.collecting_photos)

    if callback.message:
        await callback.message.answer(
            t("arrival_photo_prompt", lang),
            reply_markup=arrival_photo_keyboard(lang),
        )
    await callback.answer()


@router.message(ArrivalStates.collecting_photos, F.photo)
async def arrival_collect_photos(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    data = await state.get_data()
    photos = list(data.get("photos", []))
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)

    await message.answer(
        t("arrival_photo_done", lang, count=len(photos)),
        reply_markup=arrival_photo_keyboard(lang),
    )


@router.callback_query(ArrivalStates.collecting_photos, F.data == "arrival:no_photo")
async def arrival_without_invoice_photo(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
) -> None:
    lang = await get_user_language(db, callback.from_user)
    await state.update_data(no_invoice=True, photos=[])
    await state.set_state(ArrivalStates.manual_input)
    if callback.message:
        await callback.message.answer(t("manual_text_prompt", lang))
    await callback.answer()


@router.callback_query(ArrivalStates.collecting_photos, F.data == "arrival:photos_done")
async def arrival_photos_done(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, callback.from_user)
    data = await state.get_data()
    photos = data.get("photos", [])

    if not photos:
        if callback.message:
            await callback.message.answer(
                t("upload_photo_or_finish", lang),
                reply_markup=arrival_photo_keyboard(lang),
            )
        await callback.answer()
        return

    await state.set_state(ArrivalStates.waiting_supplier)
    if callback.message:
        await callback.message.answer(t("supplier_prompt", lang))
    await callback.answer()


@router.message(ArrivalStates.manual_input, F.text)
async def arrival_manual_text(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    manual_comment = message.text.strip()

    if not manual_comment:
        await message.answer(t("manual_text_prompt", lang))
        return

    await state.update_data(comment=manual_comment)
    await state.set_state(ArrivalStates.waiting_supplier)
    await message.answer(t("supplier_prompt", lang))


@router.message(ArrivalStates.waiting_supplier, F.text)
async def arrival_supplier(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    supplier_name = message.text.strip()

    if not supplier_name:
        await message.answer(t("supplier_prompt", lang))
        return

    await state.update_data(supplier_name=supplier_name)
    await state.set_state(ArrivalStates.waiting_date)
    await message.answer(t("date_prompt", lang))


@router.message(ArrivalStates.waiting_date, F.text)
async def arrival_date(
    message: Message,
    state: FSMContext,
    db: Database,
    request_service: RequestService,
) -> None:
    lang = await get_user_language(db, message.from_user)
    parsed_date = parse_iso_date(message.text)
    if parsed_date is None:
        await message.answer(t("date_invalid", lang))
        return

    data = await state.get_data()
    try:
        request_record = await request_service.finalize_request(
            telegram_user_id=message.from_user.id,
            telegram_user_name=message.from_user.full_name or str(message.from_user.id),
            operation_type="arrival",
            branch=data["branch"],
            warehouse=data["warehouse"],
            supplier_name=data.get("supplier_name"),
            request_date=parsed_date,
            comment=data.get("comment"),
            photos=data.get("photos", []),
        )
    except ReportDeliveryError:
        await state.clear()
        await message.answer(t("request_saved_but_not_sent", lang))
        await message.answer(t("main_menu", lang), reply_markup=main_menu_keyboard(lang))
        return
    except Exception:
        await message.answer(t("safe_error", lang))
        return

    await state.clear()
    await message.answer(t("request_success", lang, request_id=request_record["id"]))
    await message.answer(t("main_menu", lang), reply_markup=main_menu_keyboard(lang))


@router.message(ArrivalStates.selecting_branch)
@router.message(ArrivalStates.selecting_warehouse)
async def arrival_buttons_only(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("use_buttons", lang))


@router.message(ArrivalStates.collecting_photos)
async def arrival_photo_only(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("upload_photo_or_finish", lang))


@router.message(ArrivalStates.manual_input)
async def arrival_manual_text_required(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("manual_text_prompt", lang))


@router.message(ArrivalStates.waiting_supplier)
async def arrival_supplier_text_required(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("supplier_prompt", lang))


@router.message(ArrivalStates.waiting_date)
async def arrival_date_text_required(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("date_prompt", lang))
