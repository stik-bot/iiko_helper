from __future__ import annotations

import asyncio
import html
import logging
from uuid import uuid4

from aiogram import F, Router
from aiogram.types import Message

from app.config import Settings
from app.knowledge_base import KnowledgeBase
from app.services.gemini_service import GeminiQuotaError, GeminiService


logger = logging.getLogger(__name__)
router = Router()
TELEGRAM_MESSAGE_LIMIT = 4000


async def send_long_answer(message: Message, text: str) -> None:
    normalized = (text or "").strip()
    if not normalized:
        await message.answer("Не получилось сформировать ответ.")
        return

    remainder = normalized
    while remainder:
        if len(remainder) <= TELEGRAM_MESSAGE_LIMIT:
            await message.answer(remainder)
            return

        split_at = remainder.rfind("\n\n", 0, TELEGRAM_MESSAGE_LIMIT)
        if split_at == -1:
            split_at = remainder.rfind("\n", 0, TELEGRAM_MESSAGE_LIMIT)
        if split_at == -1:
            split_at = remainder.rfind(" ", 0, TELEGRAM_MESSAGE_LIMIT)
        if split_at == -1 or split_at < TELEGRAM_MESSAGE_LIMIT // 2:
            split_at = TELEGRAM_MESSAGE_LIMIT

        chunk = remainder[:split_at].strip()
        if chunk:
            await message.answer(chunk)
        remainder = remainder[split_at:].strip()


@router.message(F.photo)
async def photo_question_handler(
    message: Message,
    settings: Settings,
    knowledge_base: KnowledgeBase,
    gemini_service: GeminiService,
) -> None:
    await message.answer("Смотрю фото и разбираю вопросы...")
    photo = message.photo[-1]
    target_path = settings.storage_dir / f"{uuid4().hex}.jpg"
    await message.bot.download(photo, destination=target_path)

    caption = (message.caption or "").strip()
    if caption:
        factual_answer = knowledge_base.answer_from_facts(caption)
        if factual_answer:
            await send_long_answer(message, factual_answer)
            return

        direct_answer = knowledge_base.answer_from_guides(caption)
        if direct_answer:
            await send_long_answer(message, direct_answer)
            return

    context = knowledge_base.render_context(
        caption or "вопросы по iiko сотрудники скидки группы отделения изъятия торговое предприятие",
        limit=10,
    )
    try:
        answer = await gemini_service.answer_image_question(target_path, caption, context)
    except GeminiQuotaError as exc:
        logger.warning("Gemini quota exceeded for image question: %s", exc)
        if exc.retry_after_seconds and exc.retry_after_seconds <= 90:
            await message.answer(
                f"Лимит Gemini временно исчерпан. Подожду около {exc.retry_after_seconds} сек. и попробую обработать фото автоматически ещё раз."
            )
            await asyncio.sleep(exc.retry_after_seconds + 1)
            try:
                answer = await gemini_service.answer_image_question(target_path, caption, context)
            except GeminiQuotaError as retry_exc:
                logger.warning("Gemini quota still exceeded after retry: %s", retry_exc)
                fallback_text = (
                    "Повторная попытка тоже упёрлась в лимит Gemini.\n\n"
                    "Попробуй снова позже или отправь вопрос с картинки текстом."
                )
                if caption:
                    fallback_text += "\n\nЕсли вопрос уже есть в локальной базе, текстом бот ответит без Gemini."
                await message.answer(f"{fallback_text}\n\nПричина: <code>{html.escape(str(retry_exc))}</code>")
                return
            except Exception as retry_exc:  # noqa: BLE001
                logger.exception("Failed to answer image question after retry.")
                await message.answer(
                    f"Не смог обработать фото после повторной попытки.\n\nПричина: <code>{html.escape(str(retry_exc))}</code>"
                )
                return
        else:
            fallback_text = (
                "Сейчас лимит Gemini временно исчерпан, поэтому фото не удалось разобрать.\n\n"
                "Попробуй снова чуть позже или отправь вопрос с картинки текстом."
            )
            if caption:
                fallback_text += "\n\nЕсли вопрос уже есть в локальной базе, текстом бот ответит без Gemini."
            await message.answer(f"{fallback_text}\n\nПричина: <code>{html.escape(str(exc))}</code>")
            return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to answer image question.")
        await message.answer(f"Не смог обработать фото.\n\nПричина: <code>{html.escape(str(exc))}</code>")
        return

    await send_long_answer(message, answer)


@router.message(F.text & ~F.via_bot)
async def text_question_handler(
    message: Message,
    knowledge_base: KnowledgeBase,
    gemini_service: GeminiService,
) -> None:
    question = (message.text or "").strip()
    if not question:
        return

    factual_answer = knowledge_base.answer_from_facts(question)
    if factual_answer:
        await send_long_answer(message, factual_answer)
        return

    direct_answer = knowledge_base.answer_from_guides(question)
    if direct_answer:
        await send_long_answer(message, direct_answer)
        return

    context = knowledge_base.render_context(question)
    try:
        answer = await gemini_service.answer_text_question(question, context)
    except GeminiQuotaError as exc:
        logger.warning("Gemini quota exceeded for text question: %s", exc)
        await message.answer(
            "Сейчас лимит Gemini временно исчерпан. Попробуй отправить вопрос чуть позже.\n\n"
            f"Причина: <code>{html.escape(str(exc))}</code>"
        )
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to answer text question.")
        await message.answer(f"Не смог ответить на вопрос.\n\nПричина: <code>{html.escape(str(exc))}</code>")
        return

    await send_long_answer(message, answer)
