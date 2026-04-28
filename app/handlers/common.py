from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer(
        "Привет. Я бот по базе знаний iiko с поддержкой Gemini.\n\n"
        "Что я умею:\n"
        "1. Отвечать на текстовые вопросы по iiko.\n"
        "2. Смотреть на фото с тестами, вопросами или скриншотами.\n"
        "3. Разбирать вопросы на изображении и помогать их решать.\n\n"
        "Просто напиши вопрос или отправь фото."
    )


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(
        "Как пользоваться:\n"
        "1. Отправь текстовый вопрос по iiko.\n"
        "2. Или отправь фото со скриншотом, тестом, заданием или ошибкой.\n"
        "3. Бот проанализирует вопрос через Gemini и ответит на русском языке.\n\n"
        "Команды:\n"
        "/start\n"
        "/help\n"
        "/sources"
    )


@router.message(Command("sources"))
async def sources_handler(message: Message) -> None:
    await message.answer(
        "Бот опирается на официальные источники iiko, включая базу знаний и iikoCloud API docs.\n"
        "Если хочешь, отправь конкретный вопрос или фото с вопросами."
    )
