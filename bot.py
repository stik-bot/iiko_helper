from __future__ import annotations

import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.config import Settings, load_settings
from app.handlers.common import router as common_router
from app.handlers.qa import router as qa_router
from app.knowledge_base import KnowledgeBase
from app.services.gemini_service import GeminiService


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(settings.log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def build_dispatcher(settings: Settings) -> tuple[Bot, Dispatcher]:
    knowledge_base = KnowledgeBase(settings.knowledge_base_path)
    gemini_service = GeminiService(settings.gemini_api_key, settings.gemini_model)

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.workflow_data.update(
        settings=settings,
        knowledge_base=knowledge_base,
        gemini_service=gemini_service,
    )
    dispatcher.include_router(common_router)
    dispatcher.include_router(qa_router)
    return bot, dispatcher


async def health_handler(_: web.Request) -> web.Response:
    return web.Response(text="ok")


async def on_webhook_startup(bot: Bot, settings: Settings) -> None:
    webhook_url = f"{settings.webhook_base_url}{settings.webhook_path}"
    await bot.set_webhook(webhook_url, allowed_updates=["message"])
    logging.getLogger(__name__).info("Webhook set to %s", webhook_url)


async def on_polling_startup(bot: Bot) -> None:
    await bot.delete_webhook(drop_pending_updates=False)
    logging.getLogger(__name__).info("Webhook disabled, polling mode enabled.")


async def run_webhook(settings: Settings) -> None:
    bot, dispatcher = build_dispatcher(settings)

    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)

    webhook_handler = SimpleRequestHandler(dispatcher=dispatcher, bot=bot)
    webhook_handler.register(app, path=settings.webhook_path)
    setup_application(app, dispatcher, bot=bot)

    await on_webhook_startup(bot, settings)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "10000"))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    logging.getLogger(__name__).info("Webhook server starting on port %s", port)
    await site.start()

    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await bot.session.close()


async def run_polling(settings: Settings) -> None:
    bot, dispatcher = build_dispatcher(settings)
    await on_polling_startup(bot)
    logging.getLogger(__name__).info("iiko knowledge bot started in polling mode.")
    await dispatcher.start_polling(bot)


async def run() -> None:
    settings = load_settings()
    configure_logging(settings)

    if settings.webhook_base_url and os.getenv("PORT", "").strip():
        logging.getLogger(__name__).info("Starting in webhook mode.")
        await run_webhook(settings)
        return

    logging.getLogger(__name__).info("Starting in polling mode.")
    await run_polling(settings)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
