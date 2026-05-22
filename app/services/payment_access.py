from __future__ import annotations

import asyncio
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class ActivationResult:
    ok: bool
    paid_until_iso: str = ""
    message: str = ""


class PaymentAccessService:
    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._state_path = self.storage_dir / "payment_access_state.json"
        self._lock = asyncio.Lock()

    def _default_state(self) -> dict:
        return {"awaiting_receipt": {}, "codes": {}}

    def _load_state(self) -> dict:
        if not self._state_path.exists():
            return self._default_state()
        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception:
            return self._default_state()
        state = self._default_state()
        state["awaiting_receipt"] = raw.get("awaiting_receipt", {}) or {}
        state["codes"] = raw.get("codes", {}) or {}
        return state

    def _save_state(self, state: dict) -> None:
        self._state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    async def mark_awaiting_receipt(self, user_id: int) -> None:
        async with self._lock:
            state = self._load_state()
            state["awaiting_receipt"][str(user_id)] = utc_now().isoformat()
            self._save_state(state)

    async def is_awaiting_receipt(self, user_id: int) -> bool:
        async with self._lock:
            state = self._load_state()
            return str(user_id) in state["awaiting_receipt"]

    async def clear_awaiting_receipt(self, user_id: int) -> None:
        async with self._lock:
            state = self._load_state()
            state["awaiting_receipt"].pop(str(user_id), None)
            self._save_state(state)

    async def issue_access_code(
        self,
        *,
        user_id: int,
        username: str,
        receipt_kind: str,
        receipt_file_id: str,
        price_uzs: int,
    ) -> str:
        async with self._lock:
            state = self._load_state()
            state["awaiting_receipt"].pop(str(user_id), None)
            code = await self._generate_unique_code(state)
            state["codes"][code] = {
                "user_id": user_id,
                "username": username,
                "receipt_kind": receipt_kind,
                "receipt_file_id": receipt_file_id,
                "price_uzs": price_uzs,
                "created_at": utc_now().isoformat(),
                "activated_at": "",
                "paid_until": "",
                "used": False,
            }
            self._save_state(state)
            return code

    async def _generate_unique_code(self, state: dict) -> str:
        for _ in range(20):
            code = "VV-" + secrets.token_hex(4).upper()
            if code not in state["codes"]:
                return code
        raise RuntimeError("Не удалось создать уникальный код доступа.")

    async def activate_code(self, code: str, days: int = 30) -> ActivationResult:
        normalized = str(code or "").strip().upper()
        if not normalized:
            return ActivationResult(ok=False, message="Введите код активации.")
        async with self._lock:
            state = self._load_state()
            item = state["codes"].get(normalized)
            if not item:
                return ActivationResult(ok=False, message="Код не найден.")
            if item.get("used"):
                return ActivationResult(ok=False, message="Этот код уже был использован.")
            paid_until = utc_now() + timedelta(days=days)
            item["used"] = True
            item["activated_at"] = utc_now().isoformat()
            item["paid_until"] = paid_until.isoformat()
            state["codes"][normalized] = item
            self._save_state(state)
            return ActivationResult(ok=True, paid_until_iso=item["paid_until"], message="Подписка активирована.")
