import os
import tempfile
import unittest
from unittest import mock


class TransactionStatementTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()

        from database.init_db import initialize_database
        from services.account_service import AccountService

        initialize_database()
        self.card_id = AccountService.create_account(
            "Test Kart", "credit_card", credit_limit=10000
        )
        self.other_id = AccountService.create_account(
            "Diğer Kart", "credit_card", credit_limit=10000
        )

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def _add(self, account_id, amount, kind, description, date):
        from services.transaction_service import TransactionService

        TransactionService.add_transaction(
            account_id,
            amount,
            kind,
            "Test",
            description,
            transaction_date=date,
        )

    def test_statement_is_newest_first_and_isolated_by_account(self):
        from services.transaction_service import TransactionService

        self._add(self.card_id, 100, "expense", "Eski harcama", "2026-07-20 10:00:00")
        self._add(self.card_id, 50, "income", "İade", "2026-07-21 10:00:00")
        self._add(self.other_id, 999, "expense", "Başka kart", "2026-07-22 10:00:00")

        items = TransactionService.get_recent_for_account(self.card_id, limit=None)

        self.assertEqual([item["description"] for item in items], ["İade", "Eski harcama"])
        self.assertEqual([item["amount"] for item in items], [50.0, 100.0])
        self.assertEqual([item["date"] for item in items], ["2026-07-21", "2026-07-20"])

    def test_recent_summary_respects_limit_but_statement_does_not(self):
        from services.transaction_service import TransactionService

        for index in range(5):
            self._add(
                self.card_id,
                index + 1,
                "expense",
                f"Hareket {index}",
                f"2026-07-{index + 1:02d} 10:00:00",
            )

        self.assertEqual(len(TransactionService.get_recent_for_account(self.card_id, limit=3)), 3)
        self.assertEqual(len(TransactionService.get_recent_for_account(self.card_id, limit=None)), 5)

    def test_empty_description_falls_back_to_category(self):
        from services.transaction_service import TransactionService

        TransactionService.add_transaction(
            self.card_id, 25, "expense", "Market", "", transaction_date="2026-07-20 10:00:00"
        )
        item = TransactionService.get_recent_for_account(self.card_id, limit=None)[0]
        self.assertEqual(item["description"], "Market")

    def test_negative_limit_is_rejected(self):
        from services.transaction_service import TransactionService

        with self.assertRaisesRegex(ValueError, "negatif"):
            TransactionService.get_recent_for_account(self.card_id, limit=-1)


if __name__ == "__main__":
    unittest.main()
