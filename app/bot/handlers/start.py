from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject
from aiogram.filters.state import StateFilter
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.common import clear_inline_keyboard, ensure_user
from app.bot.i18n import SUPPORTED_LANGUAGES, TRANSLATIONS, t
from app.bot.keyboards import (
    contact_request_keyboard,
    language_keyboard,
    main_menu_keyboard,
    remove_reply_keyboard,
    start_entry_keyboard,
)
from app.bot.states import OnboardingStates
from app.db.database import Database

router = Router(name="start")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)
group_router = Router(name="start_group")
START_BUTTON_TEXTS = tuple(TRANSLATIONS["start_button"].values())


async def _ensure_avatar(bot: Bot, db: Database, telegram_id: int) -> None:
    try:
        profile_photos = await bot.get_user_profile_photos(user_id=telegram_id, limit=1)
        if profile_photos.total_count == 0:
            return
        photo = profile_photos.photos[0][-1]
        await db.update_user_avatar(
            telegram_id=telegram_id,
            file_id=photo.file_id,
            file_unique_id=photo.file_unique_id,
            width=photo.width,
            height=photo.height,
            file_size=photo.file_size,
        )
    except Exception:
        return


async def _send_phone_request(message: Message, lang: str = "uz") -> None:
    await message.answer(
        t("phone_request", lang),
        reply_markup=contact_request_keyboard(lang),
    )


async def _is_group_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    except Exception:
        return False
    return member.status in {ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR}


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    user = await ensure_user(db, message.from_user)

    await db.log_audit(
        actor_type="telegram_user",
        actor_user_id=user["id"],
        action_type="bot_start",
        entity_type="user",
        entity_id=user["id"],
        message="Пользователь открыл Telegram-бот.",
    )

    if not user.get("phone_number"):
        await state.set_state(OnboardingStates.waiting_phone)
        await _send_phone_request(message, user.get("language") or "uz")
        return

    if not user.get("language"):
        await message.answer(
            t("choose_language", "uz"),
            reply_markup=language_keyboard(),
        )
        return

    lang = user["language"]
    await message.answer(
        t("start_prompt", lang),
        reply_markup=start_entry_keyboard(lang),
    )


@router.message(OnboardingStates.waiting_phone, F.contact)
async def receive_phone_contact(
    message: Message,
    state: FSMContext,
    db: Database,
    bot: Bot,
) -> None:
    if message.contact is None or message.contact.user_id != message.from_user.id:
        await message.answer(t("share_own_phone", "uz"), reply_markup=contact_request_keyboard("uz"))
        return

    user = await ensure_user(db, message.from_user)
    updated_user = await db.update_user_contact(
        telegram_id=message.from_user.id,
        phone_number=message.contact.phone_number,
        full_name=message.from_user.full_name or str(message.from_user.id),
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        username=message.from_user.username,
    )
    await _ensure_avatar(bot, db, message.from_user.id)
    await state.clear()

    lang = (updated_user or user).get("language") or "uz"
    await db.log_audit(
        actor_type="telegram_user",
        actor_user_id=user["id"],
        action_type="phone_shared",
        entity_type="user",
        entity_id=user["id"],
        message="Пользователь отправил номер телефона в Telegram-бот.",
        meta={"phone_number": message.contact.phone_number},
    )

    await message.answer(t("phone_saved", lang), reply_markup=remove_reply_keyboard())

    if not (updated_user or user).get("language"):
        await message.answer(t("choose_language", "uz"), reply_markup=language_keyboard())
        return

    await message.answer(t("start_prompt", lang), reply_markup=start_entry_keyboard(lang))


@router.message(OnboardingStates.waiting_phone)
async def phone_required(message: Message) -> None:
    await _send_phone_request(message, "uz")


@router.message(Command("language"))
async def language_command(message: Message, state: FSMContext, db: Database) -> None:
    user = await ensure_user(db, message.from_user)
    if not user.get("phone_number"):
        await state.set_state(OnboardingStates.waiting_phone)
        await _send_phone_request(message, user.get("language") or "uz")
        return
    await state.clear()
    await message.answer(t("choose_language", "uz"), reply_markup=language_keyboard())


@router.callback_query(F.data == "menu:language")
async def language_menu_callback(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    user = await ensure_user(db, callback.from_user)
    if not user.get("phone_number"):
        await state.set_state(OnboardingStates.waiting_phone)
        if callback.message:
            await callback.message.answer(
                t("phone_request", user.get("language") or "uz"),
                reply_markup=contact_request_keyboard(user.get("language") or "uz"),
            )
        await callback.answer()
        return

    await state.clear()
    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(t("choose_language", "uz"), reply_markup=language_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("lang:"))
async def save_language(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = callback.data.split(":", 1)[1]
    if lang not in SUPPORTED_LANGUAGES:
        await callback.answer("Unsupported language", show_alert=True)
        return

    user = await ensure_user(db, callback.from_user)
    if not user.get("phone_number"):
        await state.set_state(OnboardingStates.waiting_phone)
        if callback.message:
            await callback.message.answer(
                t("phone_request", "uz"),
                reply_markup=contact_request_keyboard("uz"),
            )
        await callback.answer()
        return

    await db.update_user_language(callback.from_user.id, lang)
    await state.clear()

    await db.log_event(
        level="INFO",
        event_type="language_changed",
        message="User selected language",
        context={"telegram_user_id": callback.from_user.id, "language": lang},
    )
    await db.log_audit(
        actor_type="telegram_user",
        actor_user_id=user["id"],
        action_type="language_changed",
        entity_type="user",
        entity_id=user["id"],
        message="Пользователь изменил язык интерфейса бота.",
        meta={"language": lang},
    )

    if callback.message:
        await clear_inline_keyboard(callback)
        await callback.message.answer(t("language_saved", lang))
        await callback.message.answer(t("start_prompt", lang), reply_markup=start_entry_keyboard(lang))
    await callback.answer()


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    user = await ensure_user(db, message.from_user)
    lang = user.get("language") or "uz"
    if not user.get("phone_number"):
        await state.set_state(OnboardingStates.waiting_phone)
        await _send_phone_request(message, lang)
        return
    await message.answer(t("cancelled", lang))
    await message.answer(t("start_prompt", lang), reply_markup=start_entry_keyboard(lang))


@group_router.message(Command("setgroup"))
async def setgroup_command(
    message: Message,
    command: CommandObject,
    db: Database,
    bot: Bot,
) -> None:
    user = await ensure_user(db, message.from_user)
    lang = user.get("language") or "uz"

    if message.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        await message.answer(t("setgroup_group_only", lang))
        return

    if not await _is_group_admin(bot, message.chat.id, message.from_user.id):
        await message.answer(t("setgroup_admin_only", lang))
        return

    raw_parts = (command.args or "").strip().split(maxsplit=1) if command else []
    raw_slug = raw_parts[0] if raw_parts else ""
    warehouse_slug = db.settings.normalize_warehouse_slug(raw_slug)
    if warehouse_slug not in {"bar", "kitchen", "supplies", "meat"}:
        await message.answer(t("setgroup_unknown_warehouse", lang))
        await message.answer(t("setgroup_usage", lang))
        return

    warehouse = await db.get_warehouse_by_slug(warehouse_slug)
    if warehouse is None or not warehouse.get("is_active"):
        await message.answer(t("setgroup_unknown_warehouse", lang))
        return

    updated = await db.bind_warehouse_group(
        warehouse_id=int(warehouse["id"]),
        group_chat_id=int(message.chat.id),
        group_chat_title=message.chat.title,
    )
    if updated is None:
        await message.answer(t("safe_error", lang))
        return

    await db.log_event(
        level="INFO",
        event_type="warehouse_group_bound",
        message="Warehouse group binding updated from Telegram command",
        context={
            "warehouse_id": updated["id"],
            "warehouse_slug": updated["slug"],
            "warehouse_name": updated["name"],
            "group_chat_id": message.chat.id,
            "group_chat_title": message.chat.title,
            "telegram_user_id": message.from_user.id,
        },
    )
    await db.log_audit(
        actor_type="telegram_user",
        actor_user_id=user["id"],
        action_type="warehouse_group_bound",
        entity_type="warehouse",
        entity_id=int(updated["id"]),
        message="Пользователь привязал Telegram-группу к складу через команду /setgroup.",
        meta={
            "warehouse_slug": updated["slug"],
            "warehouse_name": updated["name"],
            "group_chat_id": message.chat.id,
            "group_chat_title": message.chat.title,
        },
    )

    await message.answer(t("setgroup_success", lang, warehouse=updated["name"]))


@router.callback_query(F.data == "action:cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.clear()
    user = await ensure_user(db, callback.from_user)
    lang = user.get("language") or "uz"
    if callback.message:
        await clear_inline_keyboard(callback)
        if not user.get("phone_number"):
            await state.set_state(OnboardingStates.waiting_phone)
            await callback.message.answer(t("phone_request", lang), reply_markup=contact_request_keyboard(lang))
            await callback.answer()
            return
        await callback.message.answer(t("cancelled", lang))
        await callback.message.answer(t("start_prompt", lang), reply_markup=start_entry_keyboard(lang))
    await callback.answer()


@router.message(StateFilter(None), F.text.in_(START_BUTTON_TEXTS))
async def start_button_entrypoint(message: Message, state: FSMContext, db: Database) -> None:
    user = await ensure_user(db, message.from_user)
    lang = user.get("language") or "uz"
    if not user.get("phone_number"):
        await state.set_state(OnboardingStates.waiting_phone)
        await _send_phone_request(message, lang)
        return
    if not user.get("language"):
        await message.answer(t("choose_language", "uz"), reply_markup=language_keyboard())
        return
    await state.clear()
    await message.answer(t("main_menu", lang), reply_markup=main_menu_keyboard(lang))


@router.message(StateFilter(None))
async def idle_entrypoint(message: Message, state: FSMContext, db: Database) -> None:
    user = await ensure_user(db, message.from_user)
    lang = user.get("language") or "uz"
    if not user.get("phone_number"):
        await state.set_state(OnboardingStates.waiting_phone)
        await _send_phone_request(message, lang)
        return
    if not user.get("language"):
        await message.answer(t("choose_language", "uz"), reply_markup=language_keyboard())
        return
    await message.answer(t("start_prompt", lang), reply_markup=start_entry_keyboard(lang))
