from __future__ import annotations

import html

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.config import Settings
from app.services.payment_access import PaymentAccessService


router = Router()


def payment_instructions(settings: Settings) -> str:
    return (
        "РћРїР»Р°С‚Р° РїРѕРґРїРёСЃРєРё РґР»СЏ СЃР°Р№С‚Р° <b>VedaVector_Iiko</b>\n\n"
        f"1. РџРµСЂРµРІРµРґРёС‚Рµ <b>{settings.payment_price_uzs:,} СЃСѓРј</b> РЅР° РєР°СЂС‚Сѓ:\n"
        f"<code>{html.escape(settings.payment_card_number)}</code>\n\n"
        f"Recipient / ФИО: <b>{html.escape(settings.payment_owner_name)}</b>\n\n"
        "2. РџРѕСЃР»Рµ РѕРїР»Р°С‚С‹ РѕС‚РїСЂР°РІСЊС‚Рµ СЃСЋРґР° <b>С„РёСЃРєР°Р»СЊРЅС‹Р№ С‡РµРє</b> С„РѕС‚Рѕ РёР»Рё С„Р°Р№Р»РѕРј.\n"
        "3. Р‘РѕС‚ РІС‹РґР°СЃС‚ РєРѕРґ Р°РєС‚РёРІР°С†РёРё.\n"
        "4. Р’РІРµРґРёС‚Рµ СЌС‚РѕС‚ РєРѕРґ РЅР° СЃР°Р№С‚Рµ Рё РїРѕР»СѓС‡РёС‚Рµ РґРѕСЃС‚СѓРї РЅР° 30 РґРЅРµР№.\n\n"
        f"РЎР°Р№С‚: {html.escape(settings.payment_site_url)}"
    )


@router.message(CommandStart())
async def start_handler(
    message: Message,
    settings: Settings,
    payment_access_service: PaymentAccessService,
) -> None:
    payload = ""
    if message.text and " " in message.text:
        payload = message.text.split(" ", 1)[1].strip()

    if payload.lower() in {"site_payment", "payment", "pay"}:
        await payment_access_service.mark_awaiting_receipt(message.from_user.id)
        await message.answer(payment_instructions(settings))
        return

    await message.answer(
        "РџСЂРёРІРµС‚. РЇ Р±РѕС‚ РґР»СЏ РїРѕРјРѕС‰Рё РїРѕ iiko Рё РѕРїР»Р°С‚С‹ РґРѕСЃС‚СѓРїР° Рє СЃР°Р№С‚Сѓ.\n\n"
        "Р§С‚Рѕ СЏ СѓРјРµСЋ:\n"
        "1. РћС‚РІРµС‡Р°С‚СЊ РЅР° РІРѕРїСЂРѕСЃС‹ РїРѕ iiko.\n"
        "2. Р Р°Р·Р±РёСЂР°С‚СЊ С„РѕС‚Рѕ Рё СЃРєСЂРёРЅС€РѕС‚С‹.\n"
        "3. РџСЂРёРЅРёРјР°С‚СЊ РѕРїР»Р°С‚Сѓ РїРѕРґРїРёСЃРєРё РґР»СЏ СЃР°Р№С‚Р° С‡РµСЂРµР· С‡РµРє Рё РІС‹РґР°РІР°С‚СЊ РєРѕРґ Р°РєС‚РёРІР°С†РёРё.\n\n"
        "Р”Р»СЏ РѕРїР»Р°С‚С‹ РїРѕРґРїРёСЃРєРё РёСЃРїРѕР»СЊР·СѓР№С‚Рµ РєРѕРјР°РЅРґСѓ /pay."
    )


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(
        "РљР°Рє РїРѕР»СЊР·РѕРІР°С‚СЊСЃСЏ:\n"
        "1. РћС‚РїСЂР°РІСЊС‚Рµ С‚РµРєСЃС‚РѕРІС‹Р№ РІРѕРїСЂРѕСЃ РїРѕ iiko.\n"
        "2. РР»Рё РѕС‚РїСЂР°РІСЊС‚Рµ С„РѕС‚Рѕ СЃРѕ СЃРєСЂРёРЅС€РѕС‚РѕРј, РѕС€РёР±РєРѕР№ РёР»Рё С‚РµСЃС‚РѕРј.\n"
        "3. Р”Р»СЏ РѕРїР»Р°С‚С‹ РїРѕРґРїРёСЃРєРё РЅР° СЃР°Р№С‚ РёСЃРїРѕР»СЊР·СѓР№С‚Рµ /pay.\n\n"
        "РљРѕРјР°РЅРґС‹:\n"
        "/start\n"
        "/help\n"
        "/sources\n"
        "/pay"
    )


@router.message(Command("sources"))
async def sources_handler(message: Message) -> None:
    await message.answer(
        "Р‘РѕС‚ РѕРїРёСЂР°РµС‚СЃСЏ РЅР° Р»РѕРєР°Р»СЊРЅСѓСЋ Р±Р°Р·Сѓ Р·РЅР°РЅРёР№ Рё РјРѕР¶РµС‚ РїРѕРјРѕРіР°С‚СЊ СЃ РІРѕРїСЂРѕСЃР°РјРё РїРѕ iiko.\n"
        "Р”Р»СЏ РѕРїР»Р°С‚С‹ РїРѕРґРїРёСЃРєРё РЅР° СЃР°Р№С‚ РёСЃРїРѕР»СЊР·СѓР№С‚Рµ /pay."
    )


@router.message(Command("pay"))
async def pay_handler(
    message: Message,
    settings: Settings,
    payment_access_service: PaymentAccessService,
) -> None:
    await payment_access_service.mark_awaiting_receipt(message.from_user.id)
    await message.answer(payment_instructions(settings))
