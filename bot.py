from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

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


async def run_health_server() -> None:
    port = os.getenv("PORT", "").strip()
    if not port:
        await asyncio.Event().wait()
        return

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await reader.read(1024)
            body = b"ok"
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/plain; charset=utf-8\r\n"
                b"Content-Length: 2\r\n"
                b"Connection: close\r\n\r\n" + body
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle_client, host="0.0.0.0", port=int(port))
    logging.getLogger(__name__).info("Health server started on port %s", port)
    async with server:
        await server.serve_forever()


async def run() -> None:
    settings = load_settings()
    configure_logging(settings)

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

    logging.getLogger(__name__).info("iiko knowledge bot started.")
    health_task = asyncio.create_task(run_health_server())
    polling_task = asyncio.create_task(dispatcher.start_polling(bot))

    done, pending = await asyncio.wait(
        {health_task, polling_task},
        return_when=asyncio.FIRST_EXCEPTION,
    )
    for task in pending:
        task.cancel()
    for task in done:
        task.result()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
