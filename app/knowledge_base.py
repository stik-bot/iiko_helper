from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class KnowledgeSource:
    title: str
    category: str
    url: str
    summary: str
    keywords: list[str]
    steps: list[str]
    answer: str


class KnowledgeBase:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.sources = self._load_sources()

    def match_sources(self, query: str, limit: int = 5) -> list[KnowledgeSource]:
        normalized = query.lower()
        scored: list[tuple[int, KnowledgeSource]] = []
        for source in self.sources:
            score = 0
            for keyword in source.keywords:
                if keyword.lower() in normalized:
                    score += 2
            if source.category.lower() in normalized:
                score += 1
            if source.title.lower() in normalized:
                score += 1
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
                f"Источник: {source.title}\n"
                f"Категория: {source.category}\n"
                f"Описание: {source.summary}\n"
                f"URL: {source.url}"
                for source in matched
            ]
        )

    def top_sources(self, query: str, limit: int = 3) -> list[KnowledgeSource]:
        return self.match_sources(query, limit=limit)

    def _load_sources(self) -> list[KnowledgeSource]:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        sources: list[KnowledgeSource] = []
        for item in payload:
            sources.append(
                KnowledgeSource(
                    title=str(item["title"]),
                    category=str(item["category"]),
                    url=str(item["url"]),
                    summary=str(item["summary"]),
                    keywords=[str(keyword) for keyword in item.get("keywords", [])],
                    steps=[str(step) for step in item.get("steps", [])],
                    answer=str(item.get("answer", "")),
                )
            )
        return sources

    def answer_from_guides(self, query: str) -> str | None:
        source = self._best_guide(query)
        if source is None:
            return None

        if not source.steps:
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
                    score += 2
            if source.title.lower() in normalized:
                score += 2
            if score > best_score:
                best_score = score
                best_source = source
        return best_source if best_score >= 2 else None

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
                    score += 2
            if source.title.lower() in normalized:
                score += 1
            if score > best_score:
                best_score = score
                best_source = source
        return best_source if best_score >= 2 else None
