from __future__ import annotations

import asyncio
import shutil
import unittest
import uuid
from pathlib import Path

from app.services.payment_access import PaymentAccessService


TEST_TMP = Path.cwd() / ".test_tmp"


class PaymentAccessServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        TEST_TMP.mkdir(exist_ok=True)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(TEST_TMP, ignore_errors=True)

    def setUp(self) -> None:
        self.root = TEST_TMP / f"{self._testMethodName}_{uuid.uuid4().hex}"
        self.root.mkdir(parents=True, exist_ok=True)
        self.service = PaymentAccessService(self.root)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def run_async(self, coro):
        return asyncio.run(coro)

    def test_issued_code_activates_once(self) -> None:
        async def scenario() -> None:
            await self.service.mark_awaiting_receipt(123)
            self.assertTrue(await self.service.is_awaiting_receipt(123))

            code = await self.service.issue_access_code(
                user_id=123,
                username="buyer",
                receipt_kind="photo",
                receipt_file_id="telegram-file-id",
                price_uzs=1000,
            )

            self.assertFalse(await self.service.is_awaiting_receipt(123))
            first = await self.service.activate_code(code.lower())
            second = await self.service.activate_code(code)

            self.assertTrue(first.ok)
            self.assertTrue(first.paid_until_iso)
            self.assertFalse(second.ok)

        self.run_async(scenario())

    def test_unknown_code_is_rejected(self) -> None:
        result = self.run_async(self.service.activate_code("VV-NOTFOUND"))

        self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()
