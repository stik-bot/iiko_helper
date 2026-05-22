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
        "Оплата подписки для сайта <b>VedaVector_Iiko</b>\n\n"
        f"1. Переведите <b>{settings.payment_price_uzs:,} сум</b> на карту:\n"
        f"<code>{html.escape(settings.payment_card_number)}</code>\n\n"
        "2. После оплаты отправьте сюда <b>фискальный чек</b> фото или файлом.\n"
        "3. Бот выдаст код активации.\n"
        "4. Введите этот код на сайте и получите доступ на 30 дней.\n\n"
        f"Сайт: {html.escape(settings.payment_site_url)}"
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
        "Привет. Я бот для помощи по iiko и оплаты доступа к сайту.\n\n"
        "Что я умею:\n"
        "1. Отвечать на вопросы по iiko.\n"
        "2. Разбирать фото и скриншоты.\n"
        "3. Принимать оплату подписки для сайта через чек и выдавать код активации.\n\n"
        "Для оплаты подписки используйте команду /pay."
    )


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(
        "Как пользоваться:\n"
        "1. Отправьте текстовый вопрос по iiko.\n"
        "2. Или отправьте фото со скриншотом, ошибкой или тестом.\n"
        "3. Для оплаты подписки на сайт используйте /pay.\n\n"
        "Команды:\n"
        "/start\n"
        "/help\n"
        "/sources\n"
        "/pay"
    )


@router.message(Command("sources"))
async def sources_handler(message: Message) -> None:
    await message.answer(
        "Бот опирается на локальную базу знаний и может помогать с вопросами по iiko.\n"
        "Для оплаты подписки на сайт используйте /pay."
    )


@router.message(Command("pay"))
async def pay_handler(
    message: Message,
    settings: Settings,
    payment_access_service: PaymentAccessService,
) -> None:
    await payment_access_service.mark_awaiting_receipt(message.from_user.id)
    await message.answer(payment_instructions(settings))
