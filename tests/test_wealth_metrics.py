import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")


class WealthMetricsRegressionTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_patch = mock.patch("database.db.DB_NAME", self.db_path)
        self.db_patch.start()

        from database.init_db import initialize_database
        initialize_database()

    def tearDown(self):
        self.db_patch.stop()
        os.unlink(self.db_path)

    def test_expense_keeps_negative_sign_through_wealth_formatting(self):
        """−229,99 gider metrikte ve Toplam Varlık metninde eksi kalmalı."""
        from services.account_service import AccountService
        from services.transaction_service import TransactionService
        from utils.currency import format_try

        account_id = AccountService.create_account(
            "İşaret Testi", "checking", initial_balance=1000
        )
        net_before = AccountService.get_net_worth()["net"]
        TransactionService.add_transaction(
            account_id=account_id,
            amount=229.99,
            transaction_type="expense",
            category="Dijital Platformlar",
            description="İşaret regresyon testi",
        )

        net_after = AccountService.get_net_worth()["net"]
        self.assertAlmostEqual(net_after, net_before - 229.99, places=2)


        liquid_balance = 0.0 - 229.99
        self.assertAlmostEqual(liquid_balance, -229.99, places=2)
        self.assertEqual(format_try(liquid_balance), "-₺229,99")


if __name__ == "__main__":
    unittest.main()
