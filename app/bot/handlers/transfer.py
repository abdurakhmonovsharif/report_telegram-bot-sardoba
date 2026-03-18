from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.common import clear_inline_keyboard, get_user_language
from app.bot.i18n import t
from app.bot.keyboards import (
    branch_keyboard,
    main_menu_keyboard,
    start_entry_keyboard,
    transfer_kind_keyboard,
    transfer_photo_keyboard,
    warehouse_keyboard,
)
from app.bot.states import TransferStates
from app.config import Settings
from app.db.database import Database
from app.services.request_service import ReportDeliveryError, RequestService

router = Router(name="transfer")
BRANCH_TRANSFER_WAREHOUSE_PLACEHOLDER = "Без склада"


@router.callback_query(TransferStates.selecting_transfer_kind, F.data.startswith("transfer:kind:"))
async def transfer_select_kind(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    lang = await get_user_language(db, callback.from_user)
    transfer_type = callback.data.rsplit(":", 1)[-1]
    branches = await db.list_bot_branches()

    if transfer_type not in {"warehouse", "branch"} or not branches:
        await callback.answer(t("use_buttons", lang), show_alert=True)
        return

    await state.update_data(
        transfer_type=transfer_type,
        transfer_kind=transfer_type,
        from_branch_id=None,
        to_branch_id=None,
        from_warehouse_id=None,
        to_warehouse_id=None,
        source_branch_id=None,
        source_branch=None,
        source_warehouse_id=None,
        source_warehouse=None,
        branch_id=None,
        branch=None,
        warehouse_id=None,
        warehouse=None,
    )

    if transfer_type == "warehouse":
        await state.set_state(TransferStates.selecting_branch)
        prompt = t("select_branch", lang)
        markup = branch_keyboard(branches, "transfer:branch", lang=lang, back_callback="transfer:back:type")
    else:
        await state.set_state(TransferStates.selecting_branch)
        prompt = t("select_destination_branch", lang)
        markup = branch_keyboard(branches, "transfer:branch", lang=lang, back_callback="transfer:back:type")

    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(prompt, reply_markup=markup)
    await callback.answer()


@router.callback_query(TransferStates.selecting_source_branch, F.data.startswith("transfer:source_branch:"))
async def transfer_select_source_branch(
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

    data = await state.get_data()
    transfer_type = data.get("transfer_type") or data.get("transfer_kind")
    if transfer_type != "branch":
        await callback.answer(t("use_buttons", lang), show_alert=True)
        return

    if data.get("branch_id") == branch_id:
        await callback.answer(t("same_branch_error", lang), show_alert=True)
        return

    await state.update_data(
        source_branch_id=branch_id,
        source_branch=branch["bot_name"],
        from_branch_id=branch_id,
        warehouse=BRANCH_TRANSFER_WAREHOUSE_PLACEHOLDER,
        warehouse_id=None,
        to_warehouse_id=None,
        source_warehouse=None,
        source_warehouse_id=None,
        from_warehouse_id=None,
    )
    await state.set_state(TransferStates.waiting_product_name)

    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(t("product_name_prompt", lang))
    await callback.answer()


@router.callback_query(TransferStates.selecting_branch, F.data.startswith("transfer:branch:"))
async def transfer_select_branch(
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

    data = await state.get_data()
    transfer_type = data.get("transfer_type") or data.get("transfer_kind")
    if transfer_type == "branch":
        branches = await db.list_bot_branches()
        await state.update_data(
            branch_id=branch_id,
            branch=branch["bot_name"],
            to_branch_id=branch_id,
        )
        await state.set_state(TransferStates.selecting_source_branch)

        if callback.message:
            await clear_inline_keyboard(callback)
            await callback.message.answer(
                t("select_source_branch", lang),
                reply_markup=branch_keyboard(
                    branches,
                    "transfer:source_branch",
                    lang=lang,
                    back_callback="transfer:back:destination_branch",
                ),
            )
        await callback.answer()
        return

    warehouses = await db.list_active_warehouses()
    if not warehouses:
        if callback.message:
            await callback.message.answer(t("no_active_warehouses", lang))
        await callback.answer()
        return

    await state.update_data(
        branch_id=branch_id,
        branch=branch["bot_name"],
        to_branch_id=branch_id,
        source_branch_id=branch_id,
        source_branch=branch["bot_name"],
        from_branch_id=branch_id,
    )
    await state.set_state(TransferStates.selecting_source_warehouse)

    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(
            t("select_source_warehouse", lang),
            reply_markup=warehouse_keyboard(
                warehouses,
                "transfer:source_warehouse",
                lang=lang,
                back_callback="transfer:back:branch",
            ),
        )
    await callback.answer()


@router.callback_query(TransferStates.selecting_source_warehouse, F.data.startswith("transfer:source_warehouse:"))
async def transfer_select_source_warehouse(
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

    warehouses = await db.list_active_warehouses()
    await state.update_data(
        source_warehouse_id=warehouse_id,
        source_warehouse=warehouse["name"],
        from_warehouse_id=warehouse_id,
    )
    await state.set_state(TransferStates.selecting_warehouse)

    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(
            t("select_destination_warehouse", lang),
            reply_markup=warehouse_keyboard(
                warehouses,
                "transfer:warehouse",
                lang=lang,
                back_callback="transfer:back:source_warehouse",
            ),
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
    try:
        warehouse_id = int(callback.data.split(":", 2)[2])
    except ValueError:
        await callback.answer(t("use_buttons", lang), show_alert=True)
        return

    warehouse = await db.get_warehouse_by_id(warehouse_id)
    if warehouse is None or not warehouse["is_active"]:
        await callback.answer(t("use_buttons", lang), show_alert=True)
        return

    data = await state.get_data()
    transfer_type = data.get("transfer_type") or data.get("transfer_kind")
    if transfer_type == "warehouse" and data.get("source_warehouse_id") == warehouse_id:
        await callback.answer(t("same_warehouse_error", lang), show_alert=True)
        return

    await state.update_data(
        warehouse_id=warehouse_id,
        warehouse=warehouse["name"],
        to_warehouse_id=warehouse_id,
    )
    await state.set_state(TransferStates.waiting_product_name)

    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(t("product_name_prompt", lang))
    await callback.answer()


@router.message(TransferStates.waiting_product_name, F.text)
async def transfer_product_name(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    product_name = message.text.strip()
    if not product_name:
        await message.answer(t("product_name_prompt", lang))
        return
    await state.update_data(product_name=product_name)
    await state.set_state(TransferStates.waiting_quantity)
    await message.answer(t("quantity_prompt", lang))


@router.message(TransferStates.waiting_quantity, F.text)
async def transfer_quantity(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    quantity = message.text.strip()
    if not quantity:
        await message.answer(t("quantity_prompt", lang))
        return
    await state.update_data(quantity=quantity, photos=[])
    await state.set_state(TransferStates.collecting_optional_photos)
    await message.answer(
        t("transfer_photo_prompt", lang),
        reply_markup=transfer_photo_keyboard(lang, back_callback="transfer:back:quantity"),
    )


@router.message(TransferStates.collecting_optional_photos, F.photo)
async def transfer_collect_photos(message: Message, state: FSMContext, db: Database) -> None:
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
            message="Пользователь загрузил фото в черновик перемещения.",
            meta={"photos_count": len(photos)},
        )

    await message.answer(
        t("arrival_photo_done", lang, count=len(photos)),
        reply_markup=transfer_photo_keyboard(lang, back_callback="transfer:back:quantity"),
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
            branch_id=data.get("branch_id"),
            warehouse_id=data.get("warehouse_id"),
            transfer_type=data.get("transfer_type") or data.get("transfer_kind"),
            from_branch_id=data.get("from_branch_id") or data.get("source_branch_id"),
            to_branch_id=data.get("to_branch_id") or data.get("branch_id"),
            from_warehouse_id=data.get("from_warehouse_id") or data.get("source_warehouse_id"),
            to_warehouse_id=data.get("to_warehouse_id") or data.get("warehouse_id"),
            transfer_kind=data.get("transfer_kind"),
            source_branch=data.get("source_branch"),
            source_branch_id=data.get("source_branch_id"),
            source_warehouse=data.get("source_warehouse"),
            source_warehouse_id=data.get("source_warehouse_id"),
            product_name=data.get("product_name"),
            quantity=data.get("quantity"),
            photos=photos,
        )
    except ReportDeliveryError:
        await state.clear()
        if callback.message:
            await clear_inline_keyboard(callback)
            await callback.message.answer(t("request_saved_but_not_sent", lang))
            await callback.message.answer(t("start_prompt", lang), reply_markup=start_entry_keyboard(lang))
        await callback.answer()
        return
    except Exception:
        if callback.message:
            await callback.message.answer(t("safe_error", lang))
        await callback.answer()
        return

    await state.clear()
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(t("request_success", lang, request_id=request_record["id"]))
        await callback.message.answer(t("start_prompt", lang), reply_markup=start_entry_keyboard(lang))
    await callback.answer()


@router.message(TransferStates.selecting_transfer_kind)
@router.message(TransferStates.selecting_source_branch)
@router.message(TransferStates.selecting_branch)
@router.message(TransferStates.selecting_source_warehouse)
@router.message(TransferStates.selecting_warehouse)
async def transfer_buttons_only(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("use_buttons", lang))


@router.message(TransferStates.waiting_product_name)
async def transfer_product_name_only(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("product_name_prompt", lang))


@router.message(TransferStates.waiting_quantity)
async def transfer_quantity_only(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("quantity_prompt", lang))

@router.message(TransferStates.collecting_optional_photos)
async def transfer_photo_or_buttons(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("transfer_photo_prompt", lang))


@router.callback_query(TransferStates.selecting_branch, F.data == "transfer:back:type")
async def transfer_back_to_type(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, callback.from_user)
    await state.update_data(
        branch_id=None,
        branch=None,
        to_branch_id=None,
        source_branch_id=None,
        source_branch=None,
        from_branch_id=None,
        warehouse_id=None,
        warehouse=None,
        to_warehouse_id=None,
        source_warehouse_id=None,
        source_warehouse=None,
        from_warehouse_id=None,
    )
    await state.set_state(TransferStates.selecting_transfer_kind)
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(
            t("select_transfer_kind", lang),
            reply_markup=transfer_kind_keyboard(lang, back_callback="nav:main_menu"),
        )
    await callback.answer()


@router.callback_query(TransferStates.selecting_source_branch, F.data == "transfer:back:destination_branch")
async def transfer_back_to_destination_branch(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, callback.from_user)
    branches = await db.list_bot_branches()
    await state.update_data(
        source_branch_id=None,
        source_branch=None,
        from_branch_id=None,
    )
    await state.set_state(TransferStates.selecting_branch)
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(
            t("select_destination_branch", lang),
            reply_markup=branch_keyboard(branches, "transfer:branch", lang=lang, back_callback="transfer:back:type"),
        )
    await callback.answer()


@router.callback_query(TransferStates.selecting_source_warehouse, F.data == "transfer:back:branch")
async def transfer_back_to_branch(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, callback.from_user)
    branches = await db.list_bot_branches()
    await state.update_data(
        source_warehouse_id=None,
        source_warehouse=None,
        from_warehouse_id=None,
        warehouse_id=None,
        warehouse=None,
        to_warehouse_id=None,
    )
    await state.set_state(TransferStates.selecting_branch)
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(
            t("select_branch", lang),
            reply_markup=branch_keyboard(branches, "transfer:branch", lang=lang, back_callback="transfer:back:type"),
        )
    await callback.answer()


@router.callback_query(TransferStates.selecting_warehouse, F.data == "transfer:back:source_warehouse")
async def transfer_back_to_source_warehouse(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, callback.from_user)
    warehouses = await db.list_active_warehouses()
    await state.update_data(
        warehouse_id=None,
        warehouse=None,
        to_warehouse_id=None,
    )
    await state.set_state(TransferStates.selecting_source_warehouse)
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(
            t("select_source_warehouse", lang),
            reply_markup=warehouse_keyboard(
                warehouses,
                "transfer:source_warehouse",
                lang=lang,
                back_callback="transfer:back:branch",
            ),
        )
    await callback.answer()


@router.callback_query(TransferStates.collecting_optional_photos, F.data == "transfer:back:quantity")
async def transfer_back_to_quantity(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, callback.from_user)
    await state.update_data(photos=[])
    await state.set_state(TransferStates.waiting_quantity)
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(t("quantity_prompt", lang))
    await callback.answer()
