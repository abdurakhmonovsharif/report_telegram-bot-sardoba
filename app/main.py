from __future__ import annotations

import asyncio

import uvicorn

from app.api.app import create_api_app
from app.bot.run import run_bot
from app.config import get_settings


async def run_all() -> None:
    settings = get_settings()
    api_app = create_api_app(settings)

    api_config = uvicorn.Config(
        app=api_app,
        
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(api_config)

    bot_task = asyncio.create_task(run_bot())
    api_task = asyncio.create_task(server.serve())

    done, pending = await asyncio.wait(
        {bot_task, api_task},
        return_when=asyncio.FIRST_EXCEPTION,
    )

    for task in pending:
        task.cancel()

    await asyncio.gather(*pending, return_exceptions=True)

    for task in done:
        exc = task.exception()
        if exc:
            raise exc


def main() -> None:
    asyncio.run(run_all())


if __name__ == "__main__":
    main()
