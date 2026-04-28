# iiko Knowledge Bot

Telegram bot on `aiogram` that:

- answers iiko questions;
- uses `Gemini` for text and image-based questions;
- accepts photos with tests, screenshots, and tasks;
- uses a local iiko knowledge base plus Gemini.

## Features

- text Q&A about iiko;
- photo test analysis, including questions with multiple answer options;
- Russian-language answers;
- source links in replies;
- ready for local run and Render deploy.

## Commands

- `/start`
- `/help`
- `/sources`

## Local Run

```powershell
python -m pip install -r requirements.txt
python bot.py
```

## Environment Variables

- `BOT_TOKEN` or `TELEGRAM_BOT_TOKEN`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `LOG_PATH`
- `LOG_LEVEL`
- `STORAGE_DIR`
- `KNOWLEDGE_BASE_PATH`

## Render Deploy

The project is prepared for Render as a web service.

- build command: `pip install -r requirements.txt`
- start command: `python bot.py`
- service type: `web`

The bot also starts a tiny health endpoint on `PORT` for Render, while the Telegram polling keeps running in the same process.

Configuration is included in [render.yaml](./render.yaml).

Required environment variables on Render:

- `BOT_TOKEN`
- `GEMINI_API_KEY`
- `GEMINI_MODEL=gemini-2.5-flash-lite`
- `LOG_LEVEL=INFO`
- `LOG_PATH=logs/iiko_knowledge_bot.log`
- `STORAGE_DIR=storage`
- `KNOWLEDGE_BASE_PATH=knowledge/iiko_sources.json`
