from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types


class GeminiQuotaError(RuntimeError):
    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class GeminiService:
    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self.fallback_models = self._build_fallback_models(model)
        self.client = genai.Client(api_key=api_key)

    async def answer_text_question(self, question: str, knowledge_context: str) -> str:
        return await asyncio.to_thread(self._answer_text_question_sync, question, knowledge_context)

    async def answer_image_question(self, image_path: Path, caption: str, knowledge_context: str) -> str:
        return await asyncio.to_thread(self._answer_image_question_sync, image_path, caption, knowledge_context)

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
            "Если это тест или вопрос с вариантами ответа, не предполагай автоматически, что правильный вариант только один. "
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
        }.get(path.suffix.lower(), "image/jpeg")

    @staticmethod
    def _is_quota_error(text: str) -> bool:
        lowered = text.lower()
        return "429" in lowered or "resource_exhausted" in lowered or "quota" in lowered

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
                if not self._is_quota_error(raw):
                    self._raise_friendly_error(exc)
        if last_error is not None:
            self._raise_friendly_error(last_error)
        raise RuntimeError("Gemini request failed without a specific error.")
