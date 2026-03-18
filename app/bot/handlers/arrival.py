from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.common import clear_inline_keyboard, get_user_language, parse_iso_date
from app.bot.i18n import t
from app.bot.keyboards import (
    arrival_photo_keyboard,
    branch_keyboard,
    main_menu_keyboard,
    optional_comment_keyboard,
    start_entry_keyboard,
    warehouse_keyboard,
)
from app.bot.states import ArrivalStates
from app.config import Settings
from app.db.database import Database
from app.services.request_service import ReportDeliveryError, RequestService

router = Router(name="arrival")


async def _submit_arrival(
    *,
    state: FSMContext,
    db: Database,
    request_service: RequestService,
    from_user,
    reply: Message,
) -> None:
    lang = await get_user_language(db, from_user)
    data = await state.get_data()
    try:
        request_record = await request_service.finalize_request(
            telegram_user_id=from_user.id,
            telegram_user_name=from_user.full_name or str(from_user.id),
            operation_type="arrival",
            branch=data["branch"],
            warehouse=data["warehouse"],
            branch_id=data.get("branch_id"),
            warehouse_id=data.get("warehouse_id"),
            supplier_name=data.get("supplier_name"),
            request_date=data.get("request_date"),
            comment=data.get("comment"),
            info_text=data.get("info_text"),
            product_name=data.get("product_name"),
            quantity=data.get("quantity"),
            photos=data.get("photos", []),
        )
    except ReportDeliveryError:
        await state.clear()
        await reply.answer(t("request_saved_but_not_sent", lang))
        await reply.answer(t("start_prompt", lang), reply_markup=start_entry_keyboard(lang))
        return
    except Exception:
        await reply.answer(t("safe_error", lang))
        return

    await state.clear()
    await reply.answer(t("request_success", lang, request_id=request_record["id"]))
    await reply.answer(t("start_prompt", lang), reply_markup=start_entry_keyboard(lang))


@router.callback_query(ArrivalStates.selecting_branch, F.data.startswith("arrival:branch:"))
async def arrival_select_branch(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    lang = await get_user_language(db, callback.from_user)
    try:
        branch_id = int(callback.data.split(":", 2)[2])
    except ValueError:
        await callback.answer(t("use_buttons", lang), show_alert=True)
        return

    branch = await db.get_branch_by_id(branch_id)
    if branch is None or not branch["is_active"]:
        await callback.answer(t("use_buttons", lang), show_alert=True)
        return

    warehouses = await db.list_active_warehouses()
    if not warehouses:
        if callback.message:
            await callback.message.answer(t("no_active_warehouses", lang))
        await callback.answer()
        return

    await state.update_data(branch_id=branch_id, branch=branch["bot_name"])
    await state.set_state(ArrivalStates.selecting_warehouse)

    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(
            t("select_warehouse", lang),
            reply_markup=warehouse_keyboard(warehouses, "arrival:warehouse", lang=lang, back_callback="arrival:back:branch"),
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
    try:
        warehouse_id = int(callback.data.split(":", 2)[2])
    except ValueError:
        await callback.answer(t("use_buttons", lang), show_alert=True)
        return

    warehouse = await db.get_warehouse_by_id(warehouse_id)
    if warehouse is None or not warehouse["is_active"]:
        await callback.answer(t("use_buttons", lang), show_alert=True)
        return

    await state.update_data(
        warehouse_id=warehouse_id,
        warehouse=warehouse["name"],
        photos=[],
        no_invoice=False,
    )
    await state.set_state(ArrivalStates.waiting_product_name)

    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(t("product_name_prompt", lang))
    await callback.answer()


@router.message(ArrivalStates.waiting_product_name, F.text)
async def arrival_product_name(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    product_name = message.text.strip()
    if not product_name:
        await message.answer(t("product_name_prompt", lang))
        return
    await state.update_data(product_name=product_name)
    await state.set_state(ArrivalStates.waiting_quantity)
    await message.answer(t("quantity_prompt", lang))


@router.message(ArrivalStates.waiting_quantity, F.text)
async def arrival_quantity(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    quantity = message.text.strip()
    if not quantity:
        await message.answer(t("quantity_prompt", lang))
        return
    await state.update_data(quantity=quantity)
    await state.set_state(ArrivalStates.collecting_photos)
    await message.answer(
        t("arrival_photo_prompt", lang),
        reply_markup=arrival_photo_keyboard(lang, back_callback="arrival:back:quantity"),
    )


@router.message(ArrivalStates.collecting_photos, F.photo)
async def arrival_collect_photos(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    data = await state.get_data()
    photos = list(data.get("photos", []))
    photo = message.photo[-1]
    photos.append(
        {
            "telegram_file_id": photo.file_id,
            "telegram_file_unique_id": photo.file_unique_id,
            "width": photo.width,
            "height": photo.height,
            "file_size": photo.file_size,
        }
    )
    await state.update_data(photos=photos)

    user = await db.get_user_by_telegram_id(message.from_user.id)
    if user:
        await db.log_audit(
            actor_type="telegram_user",
            actor_user_id=user["id"],
            action_type="request_photo_uploaded",
            entity_type="request_draft",
            message="Пользователь загрузил фото накладной в черновик операции.",
            meta={"photos_count": len(photos)},
        )

    await message.answer(
        t("arrival_photo_done", lang, count=len(photos)),
        reply_markup=arrival_photo_keyboard(lang, back_callback="arrival:back:quantity"),
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
        await clear_inline_keyboard(callback)
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
                reply_markup=arrival_photo_keyboard(lang, back_callback="arrival:back:quantity"),
            )
        await callback.answer()
        return

    await state.set_state(ArrivalStates.waiting_supplier)
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(t("supplier_prompt", lang))
    await callback.answer()


@router.message(ArrivalStates.manual_input, F.text)
async def arrival_manual_text(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    manual_info = message.text.strip()

    if not manual_info:
        await message.answer(t("manual_text_prompt", lang))
        return

    await state.update_data(info_text=manual_info)
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
async def arrival_date(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    parsed_date = parse_iso_date(message.text)
    if parsed_date is None:
        await message.answer(t("date_invalid", lang))
        return

    await state.update_data(request_date=parsed_date)
    await state.set_state(ArrivalStates.waiting_comment)
    await message.answer(
        t("arrival_comment_prompt", lang),
        reply_markup=optional_comment_keyboard("arrival", lang, back_callback="arrival:back:date"),
    )


@router.callback_query(ArrivalStates.waiting_comment, F.data == "arrival:comment_skip")
async def arrival_comment_skip(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    request_service: RequestService,
) -> None:
    await state.update_data(comment=None)
    if callback.message:
        await clear_inline_keyboard(callback)
        await _submit_arrival(
            state=state,
            db=db,
            request_service=request_service,
            from_user=callback.from_user,
            reply=callback.message,
        )
    await callback.answer()


@router.message(ArrivalStates.waiting_comment, F.text)
async def arrival_comment(
    message: Message,
    state: FSMContext,
    db: Database,
    request_service: RequestService,
) -> None:
    await state.update_data(comment=message.text.strip() or None)
    await _submit_arrival(
        state=state,
        db=db,
        request_service=request_service,
        from_user=message.from_user,
        reply=message,
    )


@router.message(ArrivalStates.selecting_branch)
@router.message(ArrivalStates.selecting_warehouse)
async def arrival_buttons_only(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("use_buttons", lang))


@router.message(ArrivalStates.waiting_product_name)
async def arrival_product_name_required(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("product_name_prompt", lang))


@router.message(ArrivalStates.waiting_quantity)
async def arrival_quantity_required(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("quantity_prompt", lang))


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


@router.callback_query(ArrivalStates.selecting_warehouse, F.data == "arrival:back:branch")
async def arrival_back_to_branch(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, callback.from_user)
    branches = await db.list_bot_branches()
    await state.update_data(branch_id=None, branch=None, warehouse_id=None, warehouse=None)
    await state.set_state(ArrivalStates.selecting_branch)
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(
            t("select_branch", lang),
            reply_markup=branch_keyboard(branches, "arrival:branch", lang=lang, back_callback="nav:main_menu"),
        )
    await callback.answer()


@router.callback_query(ArrivalStates.collecting_photos, F.data == "arrival:back:quantity")
async def arrival_back_to_quantity(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, callback.from_user)
    await state.update_data(photos=[], no_invoice=False)
    await state.set_state(ArrivalStates.waiting_quantity)
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(t("quantity_prompt", lang))
    await callback.answer()


@router.callback_query(ArrivalStates.waiting_comment, F.data == "arrival:back:date")
async def arrival_back_to_date(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, callback.from_user)
    await state.set_state(ArrivalStates.waiting_date)
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(t("date_prompt", lang))
    await callback.answer()
