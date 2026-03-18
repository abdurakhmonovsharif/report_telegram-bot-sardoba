from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.common import (
    clear_inline_keyboard,
    format_numeric_value,
    get_user_language,
    is_valid_numeric_value,
    serialize_telegram_photo,
)
from app.bot.i18n import t
from app.bot.keyboards import (
    branch_keyboard,
    main_menu_keyboard,
    start_entry_keyboard,
    transfer_kind_keyboard,
    transfer_items_keyboard,
    transfer_photo_keyboard,
    warehouse_keyboard,
)
from app.bot.states import TransferStates
from app.config import Settings
from app.db.database import Database
from app.services.request_service import ReportDeliveryError, RequestService

router = Router(name="transfer")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)
BRANCH_TRANSFER_WAREHOUSE_PLACEHOLDER = "Без склада"


def _normalize_transfer_field(value) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _build_transfer_line_item(*, product_name, quantity) -> dict[str, str]:
    normalized_product = _normalize_transfer_field(product_name)
    normalized_quantity_raw = _normalize_transfer_field(quantity)
    if not normalized_product or not normalized_quantity_raw:
        raise ValueError("Transfer line item requires product name and quantity")
    normalized_quantity = format_numeric_value(normalized_quantity_raw)
    return {
        "product_name": normalized_product,
        "quantity": normalized_quantity,
    }


def _get_transfer_line_items(data: dict) -> list[dict[str, str]]:
    line_items: list[dict[str, str]] = []
    for raw_item in data.get("line_items", []):
        if not isinstance(raw_item, dict):
            continue
        try:
            line_items.append(
                _build_transfer_line_item(
                    product_name=raw_item.get("product_name"),
                    quantity=raw_item.get("quantity"),
                )
            )
        except ValueError:
            continue
    return line_items


def _format_transfer_line_item(item: dict[str, str]) -> str:
    return f"{item['product_name']}: {item['quantity']}"


def _format_transfer_items_for_user(items: list[dict[str, str]]) -> str:
    return "\n".join(
        f"{index}. {_format_transfer_line_item(item)}"
        for index, item in enumerate(items, start=1)
    )


async def _show_transfer_items_prompt(
    *,
    reply: Message,
    state: FSMContext,
    lang: str,
) -> None:
    data = await state.get_data()
    items = _get_transfer_line_items(data)
    if not items:
        await state.set_state(TransferStates.waiting_product_name)
        await reply.answer(t("product_name_prompt", lang))
        return

    await reply.answer(
        t("transfer_items_prompt", lang, items=_format_transfer_items_for_user(items)),
        reply_markup=transfer_items_keyboard(lang, back_callback="transfer:back:quantity"),
    )


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
        line_items=[],
        current_product_name=None,
        current_quantity=None,
        photos=[],
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
        line_items=[],
        current_product_name=None,
        current_quantity=None,
        photos=[],
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
        line_items=[],
        current_product_name=None,
        current_quantity=None,
        photos=[],
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
    await state.update_data(current_product_name=product_name)
    await state.set_state(TransferStates.waiting_quantity)
    await message.answer(t("quantity_prompt", lang))


@router.message(TransferStates.waiting_quantity, F.text)
async def transfer_quantity(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    quantity = message.text.strip()
    if not quantity:
        await message.answer(t("quantity_prompt", lang))
        return
    if not is_valid_numeric_value(quantity):
        await message.answer(t("quantity_numeric_invalid", lang))
        return

    data = await state.get_data()
    try:
        line_item = _build_transfer_line_item(
            product_name=data.get("current_product_name"),
            quantity=quantity,
        )
    except ValueError:
        await state.set_state(TransferStates.waiting_product_name)
        await message.answer(t("product_name_prompt", lang))
        return

    line_items = _get_transfer_line_items(data)
    line_items.append(line_item)

    await state.update_data(
        line_items=line_items,
        current_product_name=None,
        current_quantity=None,
        photos=[],
    )
    await state.set_state(TransferStates.confirming_items)
    await _show_transfer_items_prompt(reply=message, state=state, lang=lang)


@router.callback_query(TransferStates.confirming_items, F.data == "transfer:add_more")
async def transfer_add_more_item(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, callback.from_user)
    await state.update_data(current_product_name=None, current_quantity=None)
    await state.set_state(TransferStates.waiting_product_name)
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(t("product_name_prompt", lang))
    await callback.answer()


@router.callback_query(TransferStates.confirming_items, F.data == "transfer:items_done")
async def transfer_items_done(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, callback.from_user)
    await state.update_data(photos=[])
    await state.set_state(TransferStates.collecting_optional_photos)
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(
            t("transfer_photo_prompt", lang),
            reply_markup=transfer_photo_keyboard(lang, back_callback="transfer:back:items"),
        )
    await callback.answer()


@router.callback_query(TransferStates.confirming_items, F.data == "transfer:back:quantity")
async def transfer_back_to_item_quantity(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, callback.from_user)
    data = await state.get_data()
    items = _get_transfer_line_items(data)

    if not items:
        await state.set_state(TransferStates.waiting_product_name)
        if callback.message:
            await clear_inline_keyboard(callback)
            await callback.message.answer(t("product_name_prompt", lang))
        await callback.answer()
        return

    last_item = items.pop()
    await state.update_data(
        line_items=items,
        current_product_name=last_item["product_name"],
        current_quantity=last_item["quantity"],
    )
    await state.set_state(TransferStates.waiting_quantity)
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(t("quantity_prompt", lang))
    await callback.answer()


@router.message(TransferStates.collecting_optional_photos, F.photo)
async def transfer_collect_photos(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    data = await state.get_data()
    photos = list(data.get("photos", []))
    photo = message.photo[-1]
    photos.append(serialize_telegram_photo(photo))
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
        reply_markup=transfer_photo_keyboard(lang, back_callback="transfer:back:items"),
    )


@router.callback_query(TransferStates.collecting_optional_photos, F.data == "transfer:photos_done")
async def transfer_finalize(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    request_service: RequestService,
) -> None:
    lang = await get_user_language(db, callback.from_user)
    data = await state.get_data()
    line_items = _get_transfer_line_items(data)
    if not line_items:
        await state.set_state(TransferStates.waiting_product_name)
        if callback.message:
            await clear_inline_keyboard(callback)
            await callback.message.answer(t("product_name_prompt", lang))
        await callback.answer()
        return

    photos = data.get("photos", [])
    if not photos:
        if callback.message:
            await callback.message.answer(
                t("upload_photo_or_finish", lang),
                reply_markup=transfer_photo_keyboard(lang, back_callback="transfer:back:items"),
            )
        await callback.answer()
        return

    primary_item = line_items[0]

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
            product_name=primary_item["product_name"],
            quantity=primary_item["quantity"],
            line_items=line_items,
            photos=photos,
        )
    except ReportDeliveryError as exc:
        await state.clear()
        if callback.message:
            await clear_inline_keyboard(callback)
            await callback.message.answer(t("request_saved_but_not_sent", lang, request_id=exc.request_id))
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


@router.callback_query(TransferStates.collecting_optional_photos, F.data == "transfer:photos_skip")
async def transfer_skip_photos(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, callback.from_user)
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(
            t("photo_required_error", lang),
            reply_markup=transfer_photo_keyboard(lang, back_callback="transfer:back:items"),
        )
    await state.set_state(TransferStates.collecting_optional_photos)
    await callback.answer(t("photo_required_error", lang), show_alert=True)


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


@router.message(TransferStates.confirming_items)
async def transfer_confirming_items_buttons_only(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("use_buttons", lang))


@router.message(TransferStates.collecting_optional_photos)
async def transfer_photo_or_buttons(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("upload_photo_or_finish", lang))


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


@router.callback_query(TransferStates.collecting_optional_photos, F.data == "transfer:back:items")
async def transfer_back_to_items(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, callback.from_user)
    await state.update_data(photos=[])
    await state.set_state(TransferStates.confirming_items)
    if callback.message:
        await clear_inline_keyboard(callback)
        await _show_transfer_items_prompt(reply=callback.message, state=state, lang=lang)
    await callback.answer()
