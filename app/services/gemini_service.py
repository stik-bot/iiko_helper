from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types


class GeminiQuotaError(RuntimeError):
    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


@dataclass(slots=True)
class ReceiptValidationResult:
    ok: bool
    reason: str


class GeminiService:
    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self.fallback_models = self._build_fallback_models(model)
        self.client = genai.Client(api_key=api_key)

    async def answer_text_question(self, question: str, knowledge_context: str) -> str:
        return await asyncio.to_thread(self._answer_text_question_sync, question, knowledge_context)

    async def answer_image_question(self, image_path: Path, caption: str, knowledge_context: str) -> str:
        return await asyncio.to_thread(self._answer_image_question_sync, image_path, caption, knowledge_context)

    async def validate_payment_receipt(
        self,
        receipt_path: Path,
        *,
        expected_amount_uzs: int,
        payment_card_number: str,
        payment_owner_name: str,
    ) -> ReceiptValidationResult:
        return await asyncio.to_thread(
            self._validate_payment_receipt_sync,
            receipt_path,
            expected_amount_uzs,
            payment_card_number,
            payment_owner_name,
        )

    def _answer_text_question_sync(self, question: str, knowledge_context: str) -> str:
        prompt = self._base_prompt(question, knowledge_context)
        response = self._generate_with_fallback(prompt)
        return (response.text or "").strip()

    def _answer_image_question_sync(self, image_path: Path, caption: str, knowledge_context: str) -> str:
        question = (
            caption.strip()
            if caption.strip()
            else (
                "На фото могут быть вопросы, тест или скриншот по iiko. "
                "Прочитай текст на изображении, выдели вопрос и варианты ответа."
            )
        )

        prompt = self._base_prompt(question, knowledge_context)
        prompt += (
            "\n\nЕсли на изображении несколько вопросов, ответь на каждый отдельно."
            "\nЕсли это тест, сначала перепиши вопрос."
            "\nПотом выпиши все варианты ответа, которые видны на изображении."
            "\nОбязательно проверь, может ли быть несколько правильных вариантов."
            "\nЕсли правильных вариантов несколько, перечисли все правильные варианты, а не один."
            "\nЕсли правильный вариант один, прямо напиши, что правильный вариант один."
            "\nФормат ответа для теста:"
            "\nВопрос:"
            "\nВсе варианты:"
            "\nПравильный ответ или правильные ответы:"
            "\nПочему:"
            "\nИсточники:"
        )

        response = self._generate_with_fallback(
            [
                prompt,
                types.Part.from_bytes(data=image_path.read_bytes(), mime_type=self._mime_type(image_path)),
            ]
        )
        return (response.text or "").strip()

    def _validate_payment_receipt_sync(
        self,
        receipt_path: Path,
        expected_amount_uzs: int,
        payment_card_number: str,
        payment_owner_name: str,
    ) -> ReceiptValidationResult:
        card_last4 = "".join(ch for ch in payment_card_number if ch.isdigit())[-4:]
        prompt = (
            "You are validating a Telegram payment receipt screenshot for a website subscription.\n"
            "Read the image carefully. Decide if it proves a successful payment.\n\n"
            "Required checks:\n"
            "1. The image must be a payment receipt, bank transfer receipt, fiscal check, or payment success screenshot.\n"
            f"2. The payment amount must be at least {expected_amount_uzs} UZS / сум.\n"
            "3. The payment must look completed/successful, not pending, failed, cancelled, or only a form before payment.\n"
            f"4. The recipient must be verified: the receipt must show either the destination card ending {card_last4} "
            f"or the recipient name '{payment_owner_name}'. Accept close OCR/case variants such as SAMANDAR SULTANOV, "
            "SULTANOV SAMANDAR, or Cyrillic transliteration if clearly the same person.\n"
            "5. If neither the matching card nor the matching recipient name is visible/readable, reject it.\n"
            "6. If the amount cannot be read, reject it.\n\n"
            "Reply in this exact format:\n"
            "VALID or INVALID\n"
            "Reason: one short Russian sentence."
        )
        response = self._generate_with_fallback(
            [
                prompt,
                types.Part.from_bytes(data=receipt_path.read_bytes(), mime_type=self._mime_type(receipt_path)),
            ]
        )
        text = (response.text or "").strip()
        first_line = text.splitlines()[0].strip().upper() if text else ""
        reason = text
        for line in text.splitlines():
            if line.lower().startswith("reason:"):
                reason = line.split(":", 1)[1].strip()
                break
        if not reason:
            reason = "Не удалось прочитать чек."
        return ReceiptValidationResult(ok=first_line.startswith("VALID"), reason=reason)

    @staticmethod
    def _build_fallback_models(primary_model: str) -> list[str]:
        candidates = [
            primary_model,
            "gemini-2.5-flash",
            "gemini-2.0-flash",
        ]
        models: list[str] = []
        for candidate in candidates:
            cleaned = candidate.strip()
            if cleaned and cleaned not in models:
                models.append(cleaned)
        return models

    @staticmethod
    def _base_prompt(question: str, knowledge_context: str) -> str:
        return (
            "Ты помощник по iiko. Отвечай только на русском языке. "
            "Старайся опираться на официальную базу знаний iiko и cloud API docs, которые даны ниже. "
            "Если вопрос просит инструкцию, отвечай строго пошагово, без воды, с названиями разделов меню. "
            "Не выдумывай шаги и пункты меню, которых нет в контексте. "
            "Если это тест или вопрос с вариантами ответа, не предполагай автоматически, что правильный вариант только один. "
            "Сначала проверь, может ли правильных вариантов быть несколько. "
            "Если правильных вариантов несколько, перечисли все. "
            "Если правильный вариант один, так и напиши. "
            "Для тестов не сокращай варианты и по возможности называй их так, как они написаны на изображении или в вопросе. "
            "Если в контексте есть точное локальное правило или пошаговая инструкция, считай их приоритетнее общих рассуждений. "
            "Если не хватает данных, прямо скажи, что нужен более точный раздел или версия iiko. "
            "В конце всегда добавляй блок 'Источники:' и перечисляй релевантные URL из контекста.\n\n"
            f"Вопрос пользователя:\n{question}\n\n"
            f"Контекст официальных источников:\n{knowledge_context}"
        )

    @staticmethod
    def _mime_type(path: Path) -> str:
        return {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
            ".pdf": "application/pdf",
        }.get(path.suffix.lower(), "image/jpeg")

    @staticmethod
    def _is_quota_error(text: str) -> bool:
        lowered = text.lower()
        return "429" in lowered or "resource_exhausted" in lowered or "quota" in lowered

    @staticmethod
    def _is_temporary_unavailable_error(text: str) -> bool:
        lowered = text.lower()
        return (
            "503" in lowered
            or "unavailable" in lowered
            or "high demand" in lowered
            or "try again later" in lowered
        )

    @staticmethod
    def _is_missing_model_error(text: str) -> bool:
        lowered = text.lower()
        return (
            "404" in lowered
            or "not_found" in lowered
            or ("model" in lowered and "not found" in lowered)
            or "is not found for api version" in lowered
            or "supported for generatecontent" in lowered
        )

    @staticmethod
    def _extract_retry_seconds(text: str) -> int | None:
        match = re.search(r"retry in\s+(\d+(?:\.\d+)?)s?", text, flags=re.IGNORECASE)
        if match:
            return int(float(match.group(1)))
        match = re.search(r"'retryDelay':\s*'(\d+)s'", text)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _raise_friendly_error(exc: Exception) -> None:
        raw = str(exc)
        if GeminiService._is_quota_error(raw):
            retry_after = GeminiService._extract_retry_seconds(raw)
            message = "Лимит Gemini временно исчерпан."
            if retry_after is not None:
                message += f" Попробуй снова примерно через {retry_after} сек."
            raise GeminiQuotaError(message, retry_after_seconds=retry_after) from exc
        if GeminiService._is_temporary_unavailable_error(raw):
            retry_after = GeminiService._extract_retry_seconds(raw) or 20
            message = "Gemini временно перегружен."
            message += f" Попробуй снова примерно через {retry_after} сек."
            raise GeminiQuotaError(message, retry_after_seconds=retry_after) from exc
        raise RuntimeError(raw) from exc

    def _generate_with_fallback(self, contents: Any):
        last_error: Exception | None = None
        for model_name in self.fallback_models:
            try:
                return self.client.models.generate_content(model=model_name, contents=contents)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                raw = str(exc)
                if self._is_missing_model_error(raw):
                    continue
                if not self._is_quota_error(raw) and not self._is_temporary_unavailable_error(raw):
                    self._raise_friendly_error(exc)
        if last_error is not None:
            self._raise_friendly_error(last_error)
        raise RuntimeError("Gemini request failed without a specific error.")
