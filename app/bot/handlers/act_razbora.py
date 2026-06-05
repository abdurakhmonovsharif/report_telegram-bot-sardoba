from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.common import (
    clear_inline_keyboard,
    format_numeric_value,
    get_user_language,
    is_valid_numeric_value,
    parse_iso_date,
)
from app.bot.i18n import t
from app.bot.keyboards import (
    act_razbora_items_keyboard,
    branch_keyboard,
    start_entry_keyboard,
)
from app.bot.states import ActRazboraStates
from app.config import Settings
from app.db.database import Database
from app.services.request_service import ReportDeliveryError, RequestService

router = Router(name="act_razbora")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)

ACT_RAZBORA_WAREHOUSE_PLACEHOLDER = "Без склада"


def _normalize_field(value) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _numeric_decimal(value: str) -> Decimal:
    return Decimal(value.replace(" ", ""))


def _build_nomenclature_item(*, product_name, quantity) -> dict[str, str]:
    normalized_product = _normalize_field(product_name)
    normalized_quantity_raw = _normalize_field(quantity)
    if not normalized_product or not normalized_quantity_raw:
        raise ValueError("Act razbora nomenclature item requires name and quantity")
    normalized_quantity = format_numeric_value(normalized_quantity_raw)
    return {
        "product_name": normalized_product,
        "quantity": normalized_quantity,
    }


def _get_nomenclature_items(data: dict) -> list[dict[str, str]]:
    line_items: list[dict[str, str]] = []
    for raw_item in data.get("line_items", []):
        if not isinstance(raw_item, dict):
            continue
        try:
            line_items.append(
                _build_nomenclature_item(
                    product_name=raw_item.get("product_name"),
                    quantity=raw_item.get("quantity"),
                )
            )
        except ValueError:
            continue
    return line_items


def _items_total(items: list[dict[str, str]]) -> Decimal:
    total = Decimal("0")
    for item in items:
        total += _numeric_decimal(item["quantity"])
    return total


def _format_item(item: dict[str, str]) -> str:
    return f"{item['product_name']}: {item['quantity']} kg"


async def _show_items_prompt(
    *,
    reply: Message,
    state: FSMContext,
    lang: str,
) -> None:
    data = await state.get_data()
    items = _get_nomenclature_items(data)
    items_text = (
        "\n".join(f"{index}. {_format_item(item)}" for index, item in enumerate(items, start=1))
        if items
        else t("act_razbora_no_nomenclature", lang)
    )
    await reply.answer(
        t(
            "act_razbora_items_prompt",
            lang,
            product=data.get("product_name"),
            quantity=data.get("quantity"),
            items=items_text,
        ),
        reply_markup=act_razbora_items_keyboard(
            lang,
            has_items=bool(items),
            back_callback="act_razbora:back:nomenclature_quantity",
        ),
    )


async def _submit_act_razbora(
    *,
    state: FSMContext,
    db: Database,
    request_service: RequestService,
    from_user,
    reply: Message,
) -> None:
    lang = await get_user_language(db, from_user)
    data = await state.get_data()
    product_name = _normalize_field(data.get("product_name"))
    quantity = _normalize_field(data.get("quantity"))

    if not product_name:
        await state.set_state(ActRazboraStates.waiting_product_name)
        await reply.answer(t("act_razbora_product_prompt", lang))
        return
    if not quantity:
        await state.set_state(ActRazboraStates.waiting_total_quantity)
        await reply.answer(t("act_razbora_total_quantity_prompt", lang))
        return

    try:
        request_record = await request_service.finalize_request(
            telegram_user_id=from_user.id,
            telegram_user_name=from_user.full_name or str(from_user.id),
            operation_type="act_razbora",
            branch=data["branch"],
            warehouse=data.get("warehouse") or ACT_RAZBORA_WAREHOUSE_PLACEHOLDER,
            branch_id=data.get("branch_id"),
            warehouse_id=None,
            request_date=data.get("request_date"),
            product_name=product_name,
            quantity=quantity,
            line_items=_get_nomenclature_items(data),
            photos=[],
        )
    except ReportDeliveryError as exc:
        await state.clear()
        await reply.answer(t("request_saved_but_not_sent", lang, request_id=exc.request_id))
        await reply.answer(t("start_prompt", lang), reply_markup=start_entry_keyboard(lang))
        return
    except Exception:
        await reply.answer(t("safe_error", lang))
        return

    await state.clear()
    await reply.answer(t("request_success", lang, request_id=request_record["id"]))
    await reply.answer(t("start_prompt", lang), reply_markup=start_entry_keyboard(lang))


@router.callback_query(ActRazboraStates.selecting_branch, F.data.startswith("act_razbora:branch:"))
async def act_razbora_select_branch(
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

    await state.update_data(
        branch_id=branch_id,
        branch=branch["bot_name"],
        warehouse=ACT_RAZBORA_WAREHOUSE_PLACEHOLDER,
        warehouse_id=None,
        product_name=None,
        quantity=None,
        current_nomenclature_name=None,
        current_nomenclature_quantity=None,
        line_items=[],
        request_date=None,
    )
    await state.set_state(ActRazboraStates.waiting_product_name)

    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(t("act_razbora_product_prompt", lang))
    await callback.answer()


@router.message(ActRazboraStates.waiting_product_name, F.text)
async def act_razbora_product_name(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    product_name = message.text.strip()
    if not product_name:
        await message.answer(t("act_razbora_product_prompt", lang))
        return
    await state.update_data(product_name=product_name)
    await state.set_state(ActRazboraStates.waiting_total_quantity)
    await message.answer(t("act_razbora_total_quantity_prompt", lang))


@router.message(ActRazboraStates.waiting_total_quantity, F.text)
async def act_razbora_total_quantity(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    quantity = message.text.strip()
    if not quantity:
        await message.answer(t("act_razbora_total_quantity_prompt", lang))
        return
    if not is_valid_numeric_value(quantity):
        await message.answer(t("quantity_numeric_invalid", lang))
        return

    await state.update_data(quantity=format_numeric_value(quantity), line_items=[])
    await state.set_state(ActRazboraStates.confirming_items)
    await _show_items_prompt(reply=message, state=state, lang=lang)


@router.callback_query(ActRazboraStates.confirming_items, F.data == "act_razbora:add_more")
async def act_razbora_add_nomenclature(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, callback.from_user)
    await state.update_data(current_nomenclature_name=None, current_nomenclature_quantity=None)
    await state.set_state(ActRazboraStates.waiting_nomenclature_name)
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(t("act_razbora_nomenclature_name_prompt", lang))
    await callback.answer()


@router.message(ActRazboraStates.waiting_nomenclature_name, F.text)
async def act_razbora_nomenclature_name(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    nomenclature_name = message.text.strip()
    if not nomenclature_name:
        await message.answer(t("act_razbora_nomenclature_name_prompt", lang))
        return
    await state.update_data(current_nomenclature_name=nomenclature_name)
    await state.set_state(ActRazboraStates.waiting_nomenclature_quantity)
    await message.answer(t("act_razbora_nomenclature_quantity_prompt", lang))


@router.message(ActRazboraStates.waiting_nomenclature_quantity, F.text)
async def act_razbora_nomenclature_quantity(message: Message, state: FSMContext, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    quantity = message.text.strip()
    if not quantity:
        await message.answer(t("act_razbora_nomenclature_quantity_prompt", lang))
        return
    if not is_valid_numeric_value(quantity):
        await message.answer(t("quantity_numeric_invalid", lang))
        return

    data = await state.get_data()
    try:
        line_item = _build_nomenclature_item(
            product_name=data.get("current_nomenclature_name"),
            quantity=quantity,
        )
    except ValueError:
        await state.set_state(ActRazboraStates.waiting_nomenclature_name)
        await message.answer(t("act_razbora_nomenclature_name_prompt", lang))
        return

    line_items = _get_nomenclature_items(data)
    new_total = _items_total(line_items) + _numeric_decimal(line_item["quantity"])
    total_quantity = _numeric_decimal(str(data.get("quantity") or "0"))
    if new_total > total_quantity:
        await message.answer(t("act_razbora_quantity_exceeded", lang, total=data.get("quantity")))
        return

    line_items.append(line_item)
    await state.update_data(
        line_items=line_items,
        current_nomenclature_name=None,
        current_nomenclature_quantity=None,
    )
    await state.set_state(ActRazboraStates.confirming_items)
    await _show_items_prompt(reply=message, state=state, lang=lang)


@router.callback_query(ActRazboraStates.confirming_items, F.data == "act_razbora:items_done")
async def act_razbora_finalize(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    request_service: RequestService,
) -> None:
    lang = await get_user_language(db, callback.from_user)
    data = await state.get_data()
    product_name = _normalize_field(data.get("product_name"))
    quantity = _normalize_field(data.get("quantity"))
    if not product_name:
        await state.set_state(ActRazboraStates.waiting_product_name)
        if callback.message:
            await clear_inline_keyboard(callback)
            await callback.message.answer(t("act_razbora_product_prompt", lang))
        await callback.answer()
        return
    if not quantity:
        await state.set_state(ActRazboraStates.waiting_total_quantity)
        if callback.message:
            await clear_inline_keyboard(callback)
            await callback.message.answer(t("act_razbora_total_quantity_prompt", lang))
        await callback.answer()
        return

    if not data.get("request_date"):
        await state.set_state(ActRazboraStates.waiting_date)
        if callback.message:
            await clear_inline_keyboard(callback)
            await callback.message.answer(t("date_prompt", lang))
        await callback.answer()
        return

    if callback.message:
        await clear_inline_keyboard(callback)
        await _submit_act_razbora(
            state=state,
            db=db,
            request_service=request_service,
            from_user=callback.from_user,
            reply=callback.message,
        )
    await callback.answer()


@router.message(ActRazboraStates.waiting_date, F.text)
async def act_razbora_date(
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

    await state.update_data(request_date=parsed_date)
    await _submit_act_razbora(
        state=state,
        db=db,
        request_service=request_service,
        from_user=message.from_user,
        reply=message,
    )


@router.callback_query(ActRazboraStates.confirming_items, F.data == "act_razbora:back:nomenclature_quantity")
async def act_razbora_back_to_nomenclature_quantity(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
) -> None:
    lang = await get_user_language(db, callback.from_user)
    data = await state.get_data()
    items = _get_nomenclature_items(data)

    if not items:
        await state.set_state(ActRazboraStates.waiting_total_quantity)
        if callback.message:
            await clear_inline_keyboard(callback)
            await callback.message.answer(t("act_razbora_total_quantity_prompt", lang))
        await callback.answer()
        return

    last_item = items.pop()
    await state.update_data(
        line_items=items,
        current_nomenclature_name=last_item["product_name"],
        current_nomenclature_quantity=last_item["quantity"],
    )
    await state.set_state(ActRazboraStates.waiting_nomenclature_quantity)
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(t("act_razbora_nomenclature_quantity_prompt", lang))
    await callback.answer()


@router.message(ActRazboraStates.selecting_branch)
async def act_razbora_buttons_only(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("use_buttons", lang))


@router.message(ActRazboraStates.waiting_product_name)
async def act_razbora_product_name_only(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("act_razbora_product_prompt", lang))


@router.message(ActRazboraStates.waiting_total_quantity)
async def act_razbora_total_quantity_only(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("act_razbora_total_quantity_prompt", lang))


@router.message(ActRazboraStates.waiting_nomenclature_name)
async def act_razbora_nomenclature_name_only(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("act_razbora_nomenclature_name_prompt", lang))


@router.message(ActRazboraStates.waiting_nomenclature_quantity)
async def act_razbora_nomenclature_quantity_only(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("act_razbora_nomenclature_quantity_prompt", lang))


@router.message(ActRazboraStates.waiting_date)
async def act_razbora_date_text_required(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("date_prompt", lang))


@router.message(ActRazboraStates.confirming_items)
async def act_razbora_confirming_items_buttons_only(message: Message, db: Database) -> None:
    lang = await get_user_language(db, message.from_user)
    await message.answer(t("use_buttons", lang))
