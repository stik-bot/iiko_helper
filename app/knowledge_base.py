from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


def _tokenize(text: str) -> list[str]:
    normalized = []
    for char in text.lower():
        if char.isalnum() or char in {"_", "+", "-"}:
            normalized.append(char)
        else:
            normalized.append(" ")
    return [token for token in "".join(normalized).split() if len(token) >= 3]


def _truncate(text: str, limit: int = 1800) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}..."


@dataclass(slots=True)
class KnowledgeSource:
    title: str
    category: str
    url: str
    summary: str
    keywords: list[str]
    steps: list[str]
    answer: str
    content: str

    @property
    def searchable_text(self) -> str:
        parts = [
            self.title,
            self.category,
            self.summary,
            " ".join(self.keywords),
            " ".join(self.steps),
            self.answer,
            self.content,
        ]
        return "\n".join(part for part in parts if part).lower()

    @property
    def content_excerpt(self) -> str:
        if self.content:
            return _truncate(self.content, limit=2200)
        if self.answer:
            return _truncate(self.answer, limit=900)
        if self.steps:
            return _truncate(" ".join(self.steps), limit=900)
        return self.summary


class KnowledgeBase:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.sources = self._load_sources()

    def match_sources(self, query: str, limit: int = 5) -> list[KnowledgeSource]:
        normalized = query.lower()
        query_tokens = set(_tokenize(query))
        scored: list[tuple[int, KnowledgeSource]] = []

        for source in self.sources:
            score = 0
            searchable = source.searchable_text
            source_tokens = set(_tokenize(searchable))

            for keyword in source.keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in normalized:
                    score += 4

            if source.title.lower() in normalized:
                score += 5
            if source.category.lower() in normalized:
                score += 2

            overlap = query_tokens & source_tokens
            score += sum(2 if len(token) >= 6 else 1 for token in overlap)

            if source.content and overlap:
                score += min(len(overlap), 5)

            if score:
                scored.append((score, source))

        if not scored:
            return self.sources[:limit]

        scored.sort(key=lambda item: item[0], reverse=True)
        return [source for _, source in scored[:limit]]

    def render_context(self, query: str, limit: int = 5) -> str:
        matched = self.match_sources(query, limit=limit)
        return "\n\n".join(
            [
                (
                    f"Источник: {source.title}\n"
                    f"Категория: {source.category}\n"
                    f"Описание: {source.summary}\n"
                    f"Фрагмент: {source.content_excerpt}\n"
                    f"URL: {source.url}"
                )
                for source in matched
            ]
        )

    def top_sources(self, query: str, limit: int = 3) -> list[KnowledgeSource]:
        return self.match_sources(query, limit=limit)

    def answer_from_guides(self, query: str) -> str | None:
        source = self._best_guide(query)
        if source is None or not source.steps:
            return None

        steps = "\n".join(f"{index}. {step}" for index, step in enumerate(source.steps, start=1))
        return (
            f"<b>{source.title}</b>\n\n"
            f"{source.summary}\n\n"
            f"<b>Пошагово:</b>\n{steps}\n\n"
            f"<b>Источник:</b> {source.url}"
        )

    def answer_from_facts(self, query: str) -> str | None:
        source = self._best_fact(query)
        if source is None or not source.answer:
            return None
        return (
            f"<b>{source.title}</b>\n\n"
            f"{source.answer}\n\n"
            f"<b>Источник:</b> {source.url}"
        )

    def _best_guide(self, query: str) -> KnowledgeSource | None:
        normalized = query.lower()
        best_source: KnowledgeSource | None = None
        best_score = 0
        for source in self.sources:
            if not source.steps:
                continue
            score = 0
            for keyword in source.keywords:
                if keyword.lower() in normalized:
                    score += 3
            if source.title.lower() in normalized:
                score += 3
            if score > best_score:
                best_score = score
                best_source = source
        return best_source if best_score >= 3 else None

    def _best_fact(self, query: str) -> KnowledgeSource | None:
        normalized = query.lower()
        best_source: KnowledgeSource | None = None
        best_score = 0
        for source in self.sources:
            if not source.answer:
                continue
            score = 0
            for keyword in source.keywords:
                if keyword.lower() in normalized:
                    score += 3
            if source.title.lower() in normalized:
                score += 2
            if score > best_score:
                best_score = score
                best_source = source
        return best_source if best_score >= 3 else None

    def _load_sources(self) -> list[KnowledgeSource]:
        sources: list[KnowledgeSource] = []
        for source_file in self._source_files():
            payload = json.loads(source_file.read_text(encoding="utf-8"))
            for item in payload:
                sources.append(
                    KnowledgeSource(
                        title=str(item["title"]),
                        category=str(item["category"]),
                        url=str(item["url"]),
                        summary=str(item.get("summary", "")),
                        keywords=[str(keyword) for keyword in item.get("keywords", [])],
                        steps=[str(step) for step in item.get("steps", [])],
                        answer=str(item.get("answer", "")),
                        content=str(item.get("content", "")),
                    )
                )
        return sources

    def _source_files(self) -> list[Path]:
        if self.path.is_dir():
            return sorted(self.path.glob("*.json"))

        if self.path.exists():
            return sorted(self.path.parent.glob("*.json"))

        self.path.parent.mkdir(parents=True, exist_ok=True)
        return []
