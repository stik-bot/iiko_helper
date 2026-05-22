from __future__ import annotations

import asyncio
import logging
import os

from aiohttp import ClientSession, web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.config import Settings, load_settings
from app.handlers.common import router as common_router
from app.handlers.qa import router as qa_router
from app.knowledge_base import KnowledgeBase
from app.services.gemini_service import GeminiService
from app.services.payment_access import PaymentAccessService


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(settings.log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def build_dispatcher(settings: Settings) -> tuple[Bot, Dispatcher, PaymentAccessService]:
    knowledge_base = KnowledgeBase(settings.knowledge_base_path)
    gemini_service = GeminiService(settings.gemini_api_key, settings.gemini_model)
    payment_access_service = PaymentAccessService(settings.storage_dir)

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.workflow_data.update(
        settings=settings,
        knowledge_base=knowledge_base,
        gemini_service=gemini_service,
        payment_access_service=payment_access_service,
    )
    dispatcher.include_router(common_router)
    dispatcher.include_router(qa_router)
    return bot, dispatcher, payment_access_service


async def health_handler(_: web.Request) -> web.Response:
    return web.Response(text="ok")


def json_response(payload: dict, status: int = 200) -> web.Response:
    response = web.json_response(payload, status=status)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return response


async def payment_activate_handler(request: web.Request) -> web.Response:
    if request.method == "OPTIONS":
        return json_response({"ok": True})

    service: PaymentAccessService = request.app["payment_access_service"]
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        payload = {}
    code = str(payload.get("code", "")).strip()
    result = await service.activate_code(code)
    if not result.ok:
        return json_response({"ok": False, "message": result.message}, status=400)
    return json_response({"ok": True, "paid_until": result.paid_until_iso, "message": result.message})


async def on_webhook_startup(bot: Bot, settings: Settings) -> None:
    webhook_url = f"{settings.webhook_base_url}{settings.webhook_path}"
    await bot.set_webhook(webhook_url, allowed_updates=["message"])
    logging.getLogger(__name__).info("Webhook set to %s", webhook_url)


async def on_polling_startup(bot: Bot) -> None:
    await bot.delete_webhook(drop_pending_updates=False)
    logging.getLogger(__name__).info("Webhook disabled, polling mode enabled.")


async def start_health_server(port: int, app: web.Application) -> web.AppRunner:
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_route("POST", "/payment/activate", payment_activate_handler)
    app.router.add_route("OPTIONS", "/payment/activate", payment_activate_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    logging.getLogger(__name__).info("Health server started on port %s", port)
    return runner


async def keep_service_awake(settings: Settings) -> None:
    if not settings.webhook_base_url:
        return

    health_url = f"{settings.webhook_base_url.rstrip('/')}/health"
    logger = logging.getLogger(__name__)

    async with ClientSession() as session:
        while True:
            try:
                async with session.get(health_url, timeout=20) as response:
                    logger.info("Self-ping %s -> %s", health_url, response.status)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Self-ping failed: %s", exc)
            await asyncio.sleep(300)


async def run_polling(settings: Settings) -> None:
    bot, dispatcher, _payment_access_service = build_dispatcher(settings)
    await on_polling_startup(bot)
    logging.getLogger(__name__).info("iiko knowledge bot started in polling mode.")
    await dispatcher.start_polling(bot)


async def run_render_service(settings: Settings) -> None:
    bot, dispatcher, payment_access_service = build_dispatcher(settings)
    app = web.Application()
    app["payment_access_service"] = payment_access_service

    webhook_handler = SimpleRequestHandler(dispatcher=dispatcher, bot=bot)
    webhook_handler.register(app, path=settings.webhook_path)
    setup_application(app, dispatcher, bot=bot)

    port = int(os.getenv("PORT", "10000"))
    runner = await start_health_server(port, app)
    keepalive_task = asyncio.create_task(keep_service_awake(settings))

    await on_webhook_startup(bot, settings)
    logging.getLogger(__name__).info("Starting Render web service mode with Telegram webhook.")
    try:
        await asyncio.Event().wait()
    finally:
        keepalive_task.cancel()
        await runner.cleanup()
        await bot.session.close()


async def run() -> None:
    settings = load_settings()
    configure_logging(settings)

    if os.getenv("PORT", "").strip():
        logging.getLogger(__name__).info("Starting in Render service mode.")
        await run_render_service(settings)
        return

    logging.getLogger(__name__).info("Starting in polling mode.")
    await run_polling(settings)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
