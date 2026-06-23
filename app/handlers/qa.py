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
from app.services.payment_access import PaymentAccessService


logger = logging.getLogger(__name__)
router = Router()
TELEGRAM_MESSAGE_LIMIT = 4000


async def send_long_answer(message: Message, text: str) -> None:
    normalized = (text or "").strip()
    if not normalized:
        await message.answer("РќРµ РїРѕР»СѓС‡РёР»РѕСЃСЊ СЃС„РѕСЂРјРёСЂРѕРІР°С‚СЊ РѕС‚РІРµС‚.")
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


async def try_issue_payment_code(
    message: Message,
    *,
    payment_access_service: PaymentAccessService,
    settings: Settings,
    gemini_service: GeminiService,
    receipt_kind: str,
    receipt_file_id: str,
    receipt_path,
) -> bool:
    if not await payment_access_service.is_awaiting_receipt(message.from_user.id):
        return False

    await message.answer("Р§РµРє РїРѕР»СѓС‡РµРЅ. РџСЂРѕРІРµСЂСЏСЋ СЃСѓРјРјСѓ Рё СЃС‚Р°С‚СѓСЃ РѕРїР»Р°С‚С‹...")
    try:
        validation = await gemini_service.validate_payment_receipt(
            receipt_path,
            expected_amount_uzs=settings.payment_price_uzs,
            payment_card_number=settings.payment_card_number,
            payment_owner_name=settings.payment_owner_name,
        )
    except GeminiQuotaError as exc:
        logger.warning("Gemini quota exceeded while validating payment receipt: %s", exc)
        await message.answer(
            "РЎРµР№С‡Р°СЃ РЅРµ РјРѕРіСѓ РїСЂРѕРІРµСЂРёС‚СЊ С‡РµРє РёР·-Р·Р° РІСЂРµРјРµРЅРЅРѕРіРѕ Р»РёРјРёС‚Р° Gemini. РљРѕРґ РЅРµ РІС‹РґР°РЅ.\n\n"
            "РћС‚РїСЂР°РІСЊС‚Рµ С‡РµРє РµС‰Рµ СЂР°Р· С‡СѓС‚СЊ РїРѕР·Р¶Рµ."
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to validate payment receipt.")
        await message.answer(
            "РќРµ СЃРјРѕРі РїСЂРѕРІРµСЂРёС‚СЊ С‡РµРє, РїРѕСЌС‚РѕРјСѓ РєРѕРґ РЅРµ РІС‹РґР°РЅ.\n\n"
            f"РџСЂРёС‡РёРЅР°: <code>{html.escape(str(exc))}</code>"
        )
        return True

    if not validation.ok:
        await message.answer(
            "РљРѕРґ РЅРµ РІС‹РґР°РЅ: С‡РµРє РЅРµ РїСЂРѕС€РµР» РїСЂРѕРІРµСЂРєСѓ.\n\n"
            f"РџСЂРёС‡РёРЅР°: <code>{html.escape(validation.reason)}</code>\n\n"
            f"РќСѓР¶РµРЅ С‡РµРє СѓСЃРїРµС€РЅРѕР№ РѕРїР»Р°С‚С‹ РЅР° СЃСѓРјРјСѓ <b>{settings.payment_price_uzs:,} СЃСѓРј</b>. "
            "РћС‚РїСЂР°РІСЊС‚Рµ РєРѕСЂСЂРµРєС‚РЅС‹Р№ СЃРєСЂРёРЅС€РѕС‚ РёР»Рё С„Р°Р№Р» С‡РµРєР°."
        )
        return True

    code = await payment_access_service.issue_access_code(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        receipt_kind=receipt_kind,
        receipt_file_id=receipt_file_id,
        price_uzs=settings.payment_price_uzs,
    )
    await message.answer(
        "Р§РµРє РїРѕР»СѓС‡РµРЅ.\n\n"
        f"Р’Р°С€ РєРѕРґ Р°РєС‚РёРІР°С†РёРё: <code>{html.escape(code)}</code>\n\n"
        "Р’РµСЂРЅРёС‚РµСЃСЊ РЅР° СЃР°Р№С‚, РѕС‚РєСЂРѕР№С‚Рµ РѕРїР»Р°С‚Сѓ, РІСЃС‚Р°РІСЊС‚Рµ СЌС‚РѕС‚ РєРѕРґ Рё Р°РєС‚РёРІРёСЂСѓР№С‚Рµ РґРѕСЃС‚СѓРї РЅР° 30 РґРЅРµР№."
    )
    return True


@router.message(F.photo)
async def photo_question_handler(
    message: Message,
    settings: Settings,
    knowledge_base: KnowledgeBase,
    gemini_service: GeminiService,
    payment_access_service: PaymentAccessService,
) -> None:
    photo = message.photo[-1]
    target_path = settings.storage_dir / f"{uuid4().hex}.jpg"
    await message.bot.download(photo, destination=target_path)

    if await try_issue_payment_code(
        message,
        payment_access_service=payment_access_service,
        settings=settings,
        gemini_service=gemini_service,
        receipt_kind="photo",
        receipt_file_id=photo.file_id,
        receipt_path=target_path,
    ):
        return

    await message.answer("РЎРјРѕС‚СЂСЋ С„РѕС‚Рѕ Рё СЂР°Р·Р±РёСЂР°СЋ РІРѕРїСЂРѕСЃ...")
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

    context = knowledge_base.render_context(caption or "РІРѕРїСЂРѕСЃС‹ РїРѕ iiko", limit=10)
    try:
        answer = await gemini_service.answer_image_question(target_path, caption, context)
    except GeminiQuotaError as exc:
        logger.warning("Gemini quota exceeded for image question: %s", exc)
        if exc.retry_after_seconds and exc.retry_after_seconds <= 90:
            await message.answer(
                f"Р›РёРјРёС‚ Gemini РІСЂРµРјРµРЅРЅРѕ РёСЃС‡РµСЂРїР°РЅ. РџРѕРґРѕР¶РґСѓ РѕРєРѕР»Рѕ {exc.retry_after_seconds} СЃРµРє. Рё РїРѕРїСЂРѕР±СѓСЋ РѕР±СЂР°Р±РѕС‚Р°С‚СЊ С„РѕС‚Рѕ РµС‰С‘ СЂР°Р·."
            )
            await asyncio.sleep(exc.retry_after_seconds + 1)
            try:
                answer = await gemini_service.answer_image_question(target_path, caption, context)
            except GeminiQuotaError as retry_exc:
                logger.warning("Gemini quota still exceeded after retry: %s", retry_exc)
                await message.answer(
                    "РџРѕРІС‚РѕСЂРЅР°СЏ РїРѕРїС‹С‚РєР° С‚РѕР¶Рµ СѓРїС‘СЂР»Р°СЃСЊ РІ Р»РёРјРёС‚ Gemini.\n\n"
                    "РџРѕРїСЂРѕР±СѓР№С‚Рµ РїРѕР·Р¶Рµ РёР»Рё РѕС‚РїСЂР°РІСЊС‚Рµ РІРѕРїСЂРѕСЃ РїРѕ С„РѕС‚Рѕ С‚РµРєСЃС‚РѕРј.\n\n"
                    f"РџСЂРёС‡РёРЅР°: <code>{html.escape(str(retry_exc))}</code>"
                )
                return
            except Exception as retry_exc:  # noqa: BLE001
                logger.exception("Failed to answer image question after retry.")
                await message.answer(
                    "РќРµ СЃРјРѕРі РѕР±СЂР°Р±РѕС‚Р°С‚СЊ С„РѕС‚Рѕ РїРѕСЃР»Рµ РїРѕРІС‚РѕСЂРЅРѕР№ РїРѕРїС‹С‚РєРё.\n\n"
                    f"РџСЂРёС‡РёРЅР°: <code>{html.escape(str(retry_exc))}</code>"
                )
                return
        else:
            await message.answer(
                "РЎРµР№С‡Р°СЃ Р»РёРјРёС‚ Gemini РІСЂРµРјРµРЅРЅРѕ РёСЃС‡РµСЂРїР°РЅ, РїРѕСЌС‚РѕРјСѓ С„РѕС‚Рѕ РЅРµ СѓРґР°Р»РѕСЃСЊ СЂР°Р·РѕР±СЂР°С‚СЊ.\n\n"
                "РџРѕРїСЂРѕР±СѓР№С‚Рµ РїРѕР·Р¶Рµ РёР»Рё РѕС‚РїСЂР°РІСЊС‚Рµ РІРѕРїСЂРѕСЃ РїРѕ С„РѕС‚Рѕ С‚РµРєСЃС‚РѕРј.\n\n"
                f"РџСЂРёС‡РёРЅР°: <code>{html.escape(str(exc))}</code>"
            )
            return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to answer image question.")
        await message.answer(f"РќРµ СЃРјРѕРі РѕР±СЂР°Р±РѕС‚Р°С‚СЊ С„РѕС‚Рѕ.\n\nРџСЂРёС‡РёРЅР°: <code>{html.escape(str(exc))}</code>")
        return

    await send_long_answer(message, answer)


@router.message(F.document)
async def document_handler(
    message: Message,
    settings: Settings,
    gemini_service: GeminiService,
    payment_access_service: PaymentAccessService,
) -> None:
    file_name = message.document.file_name or "receipt"
    suffix = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ".bin"
    target_path = settings.storage_dir / f"{uuid4().hex}{suffix}"
    await message.bot.download(message.document, destination=target_path)

    if await try_issue_payment_code(
        message,
        payment_access_service=payment_access_service,
        settings=settings,
        gemini_service=gemini_service,
        receipt_kind="document",
        receipt_file_id=message.document.file_id,
        receipt_path=target_path,
    ):
        return
    await message.answer("Р”РѕРєСѓРјРµРЅС‚ РїРѕР»СѓС‡РµРЅ. Р”Р»СЏ РѕРїР»Р°С‚С‹ РёСЃРїРѕР»СЊР·СѓР№С‚Рµ /pay, РґР»СЏ РІРѕРїСЂРѕСЃРѕРІ РѕС‚РїСЂР°РІСЊС‚Рµ С‚РµРєСЃС‚ РёР»Рё С„РѕС‚Рѕ.")


@router.message(F.text & ~F.via_bot)
async def text_question_handler(
    message: Message,
    knowledge_base: KnowledgeBase,
    gemini_service: GeminiService,
    payment_access_service: PaymentAccessService,
) -> None:
    if await payment_access_service.is_awaiting_receipt(message.from_user.id):
        await message.answer("РЇ Р¶РґСѓ РѕС‚ РІР°СЃ С„РёСЃРєР°Р»СЊРЅС‹Р№ С‡РµРє. РћС‚РїСЂР°РІСЊС‚Рµ РµРіРѕ С„РѕС‚Рѕ РёР»Рё С„Р°Р№Р»РѕРј, Рё СЏ РІС‹РґР°Рј РєРѕРґ Р°РєС‚РёРІР°С†РёРё.")
        return

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
            "РЎРµР№С‡Р°СЃ Р»РёРјРёС‚ Gemini РІСЂРµРјРµРЅРЅРѕ РёСЃС‡РµСЂРїР°РЅ. РџРѕРїСЂРѕР±СѓР№С‚Рµ РѕС‚РїСЂР°РІРёС‚СЊ РІРѕРїСЂРѕСЃ С‡СѓС‚СЊ РїРѕР·Р¶Рµ.\n\n"
            f"РџСЂРёС‡РёРЅР°: <code>{html.escape(str(exc))}</code>"
        )
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to answer text question.")
        await message.answer(f"РќРµ СЃРјРѕРі РѕС‚РІРµС‚РёС‚СЊ РЅР° РІРѕРїСЂРѕСЃ.\n\nРџСЂРёС‡РёРЅР°: <code>{html.escape(str(exc))}</code>")
        return

    await send_long_answer(message, answer)
