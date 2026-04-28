# iiko Knowledge Bot

Telegram-бот на `aiogram`, который:

- отвечает на вопросы по iiko;
- использует `Gemini` для анализа текстовых вопросов;
- принимает фото с тестами, вопросами и скриншотами;
- подсказывает ответы по локальной базе знаний и через Gemini.

## Возможности

- текстовые вопросы по iiko;
- разбор фото с тестами и несколькими вариантами ответа;
- ответы на русском языке;
- ссылки на релевантные источники в ответе;
- готовность к запуску локально и на Railway.

## Команды

- `/start`
- `/help`
- `/sources`

## Локальный запуск

```powershell
python -m pip install -r requirements.txt
python bot.py
```

## Переменные окружения

- `BOT_TOKEN` или `TELEGRAM_BOT_TOKEN`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `LOG_PATH`
- `LOG_LEVEL`
- `STORAGE_DIR`
- `KNOWLEDGE_BASE_PATH`

## Railway Deploy

Проект уже подготовлен под Railway:

- зависимости берутся из `requirements.txt`;
- worker-команда задана как `python bot.py`;
- добавлены `Procfile` и `railway.json`.

Нужно указать в Railway такие переменные:

- `BOT_TOKEN`
- `GEMINI_API_KEY`
- `GEMINI_MODEL=gemini-2.5-flash-lite`
- `LOG_LEVEL=INFO`
- `LOG_PATH=logs/iiko_knowledge_bot.log`
- `STORAGE_DIR=storage`
- `KNOWLEDGE_BASE_PATH=knowledge/iiko_sources.json`
