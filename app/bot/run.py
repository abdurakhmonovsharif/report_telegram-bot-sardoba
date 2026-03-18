from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats

from app.bot.handlers import arrival, menu, start, transfer
from app.bot.middlewares.error_middleware import ErrorLoggingMiddleware
from app.config import get_settings
from app.db.database import Database
from app.services.report_sender import ReportSender
from app.services.request_service import RequestService


def build_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.middleware(ErrorLoggingMiddleware())

    dispatcher.include_router(start.router)
    dispatcher.include_router(menu.router)
    dispatcher.include_router(arrival.router)
    dispatcher.include_router(transfer.router)
    return dispatcher


async def run_bot() -> None:
    settings = get_settings()
    db = Database(settings)
    await db.connect()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    report_sender = ReportSender(bot=bot, settings=settings, db=db)
    request_service = RequestService(db=db, report_sender=report_sender)
    dispatcher = build_dispatcher()

    try:
        if settings.telegram_mode.lower() != "polling":
            raise RuntimeError(
                "Only polling mode is implemented in this runner. "
                "Set TELEGRAM_MODE=polling."
            )

        try:
            await db.log_event(
                level="INFO",
                event_type="bot_startup",
                message="Bot is starting in polling mode",
            )
        except Exception:
            pass

        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_my_commands(
            commands=[
                BotCommand(command="start", description="Запустить бота"),
                BotCommand(command="language", description="Выбрать язык"),
                BotCommand(command="cancel", description="Отменить текущее действие"),
            ],
            scope=BotCommandScopeAllPrivateChats(),
        )
        await bot.set_my_commands(
            commands=[
                BotCommand(command="setgroup", description="Привязать текущую группу к складу"),
            ],
            scope=BotCommandScopeAllGroupChats(),
        )
        await dispatcher.start_polling(
            bot,
            db=db,
            settings=settings,
            request_service=request_service,
        )
    finally:
        try:
            await db.log_event(
                level="INFO",
                event_type="bot_shutdown",
                message="Bot polling stopped",
            )
        except Exception:
            pass
        await bot.session.close()
        await db.disconnect()


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
