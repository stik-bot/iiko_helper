from __future__ import annotations

import asyncio
import logging

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
    await dispatcher.start_polling(bot)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
