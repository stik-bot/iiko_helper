from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

DEFAULT_PAYMENT_PRICE_UZS = 100_000


@dataclass(slots=True)
class Settings:
    telegram_bot_token: str
    gemini_api_key: str
    gemini_model: str
    log_path: Path
    log_level: str
    storage_dir: Path
    knowledge_base_path: Path
    webhook_base_url: str
    webhook_path: str
    payment_card_number: str
    payment_price_uzs: int
    payment_owner_name: str
    payment_bot_username: str
    payment_site_url: str


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip() or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite").strip() or "gemini-2.5-flash-lite"
    log_path = Path(os.getenv("LOG_PATH", "logs/iiko_knowledge_bot.log")).resolve()
    storage_dir = Path(os.getenv("STORAGE_DIR", "storage")).resolve()
    knowledge_base_path = Path(os.getenv("KNOWLEDGE_BASE_PATH", "knowledge/iiko_sources.json")).resolve()
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
    webhook_base_url = os.getenv("WEBHOOK_BASE_URL", "").strip().rstrip("/")
    webhook_path = os.getenv("WEBHOOK_PATH", "/telegram/webhook").strip() or "/telegram/webhook"
    payment_card_number = os.getenv("PAYMENT_CARD_NUMBER", "9860160602619274").strip()
    configured_payment_price_uzs = int(os.getenv("PAYMENT_PRICE_UZS", str(DEFAULT_PAYMENT_PRICE_UZS)).strip() or str(DEFAULT_PAYMENT_PRICE_UZS))
    payment_price_uzs = max(DEFAULT_PAYMENT_PRICE_UZS, configured_payment_price_uzs)
    payment_owner_name = os.getenv("PAYMENT_OWNER_NAME", "Sultanov Samandar").strip() or "Sultanov Samandar"
    payment_bot_username = os.getenv("PAYMENT_BOT_USERNAME", "Sct_xo_Payment_BOT").strip() or "Sct_xo_Payment_BOT"
    payment_site_url = os.getenv("PAYMENT_SITE_URL", "https://vedavector-iiko.netlify.app").strip()

    if not token:
        raise ValueError("BOT_TOKEN or TELEGRAM_BOT_TOKEN is required.")
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY is required.")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    storage_dir.mkdir(parents=True, exist_ok=True)
    knowledge_base_path.parent.mkdir(parents=True, exist_ok=True)

    return Settings(
        telegram_bot_token=token,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        log_path=log_path,
        log_level=log_level,
        storage_dir=storage_dir,
        knowledge_base_path=knowledge_base_path,
        webhook_base_url=webhook_base_url,
        webhook_path=webhook_path,
        payment_card_number=payment_card_number,
        payment_price_uzs=payment_price_uzs,
        payment_owner_name=payment_owner_name,
        payment_bot_username=payment_bot_username,
        payment_site_url=payment_site_url,
    )
