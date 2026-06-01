# iiko Knowledge Bot

Telegram bot on `aiogram` that:

- answers iiko questions;
- uses `Gemini` for text and image-based questions;
- accepts photos with tests, screenshots, and tasks;
- uses a local iiko knowledge base plus Gemini;
- accepts payment receipt screenshots and issues one-time site activation codes;
- can use local certification materials synced from iiko iSpring Learn.

## Features

- text Q&A about iiko;
- photo test analysis, including questions with multiple answer options;
- Russian-language answers;
- source links in replies;
- extended local context from iiko certification materials;
- `/pay` flow for site subscriptions: card instructions, receipt upload, one-time code, and `/payment/activate` API;
- ready for local run and Render deploy.

## Commands

- `/start`
- `/help`
- `/sources`
- `/pay`

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
- `WEBHOOK_BASE_URL`
- `WEBHOOK_PATH`
- `PAYMENT_CARD_NUMBER`
- `PAYMENT_PRICE_UZS`
- `PAYMENT_BOT_USERNAME`
- `PAYMENT_SITE_URL`
- `ISPRING_LOGIN` (optional, for syncing certification materials)
- `ISPRING_PASSWORD` (optional, for syncing certification materials)

## Site Payment Flow

The static site opens Telegram with:

```text
https://t.me/<PAYMENT_BOT_USERNAME>?start=site_payment
```

The bot marks the user as waiting for a receipt. After the user sends a receipt screenshot or file, the bot creates a code like `VV-1A2B3C4D`.

The site activates that code through the bot web service:

```http
POST /payment/activate
Content-Type: application/json

{"code":"VV-1A2B3C4D"}
```

Codes are one-time use and grant 30 days of access. The site also reads `/payment/config` so the bot username and price stay in sync with Render environment variables.

## Sync Certification Materials

To refresh the local certification knowledge from iiko iSpring Learn:

```powershell
$env:ISPRING_LOGIN="your_login"
$env:ISPRING_PASSWORD="your_password"
python scripts/sync_ispring_certification.py
```

The script writes the synced dataset to `knowledge/ispring_certification.json`.

## Render Deploy

The project is prepared for Render as a web service.

- build command: `pip install -r requirements.txt`
- start command: `python bot.py`
- service type: `web`

The bot also starts a tiny health endpoint on `PORT` for Render, while the Telegram polling keeps running in the same process.

On Render, it is better to use Telegram webhook mode instead of long polling.
Set:

- `WEBHOOK_BASE_URL=https://iiko-helper-bot.onrender.com`
- `WEBHOOK_PATH=/telegram/webhook`

Configuration is included in [render.yaml](./render.yaml).

Required environment variables on Render:

- `BOT_TOKEN`
- `GEMINI_API_KEY`
- `GEMINI_MODEL=gemini-2.5-flash-lite`
- `LOG_LEVEL=INFO`
- `LOG_PATH=logs/iiko_knowledge_bot.log`
- `STORAGE_DIR=storage`
- `KNOWLEDGE_BASE_PATH=knowledge/iiko_sources.json`
- `PAYMENT_CARD_NUMBER=9860160602619274`
- `PAYMENT_PRICE_UZS=1000`
- `PAYMENT_BOT_USERNAME=Sct_xo_Payment_BOT`
- `PAYMENT_SITE_URL=https://vedavector-iiko.netlify.app`
