import os
import sqlite3
import tempfile
import unittest
from unittest import mock


class CardControlTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_patch = mock.patch("database.db.DB_NAME", self.db_path)
        self.db_patch.start()

        from database.init_db import initialize_database
        initialize_database()

    def tearDown(self):
        self.db_patch.stop()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_legacy_database_migration_is_idempotent_and_backfills_defaults(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("DROP TABLE accounts")
        conn.execute(
            """
            CREATE TABLE accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                balance REAL DEFAULT 0
            )
            """
        )
        conn.executemany(
            "INSERT INTO accounts(name, type, balance) VALUES (?, ?, ?)",
            [("Eski Hesap", "bank", 1000), ("Eski Kart", "credit", -250)],
        )
        conn.commit()
        conn.close()

        from database.init_db import initialize_database
        initialize_database()
        initialize_database()

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        columns = {
            row[1]: row for row in conn.execute("PRAGMA table_info(accounts)")
        }
        rows = conn.execute(
            "SELECT is_frozen, online_payments_enabled FROM accounts ORDER BY id"
        ).fetchall()
        conn.close()

        self.assertIn("is_frozen", columns)
        self.assertIn("online_payments_enabled", columns)
        self.assertEqual(
            [(row["is_frozen"], row["online_payments_enabled"]) for row in rows],
            [(0, 1), (0, 1)],
        )

    def test_frozen_state_persists_and_blocks_income_expense_and_installments(self):
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        card_id = AccountService.create_account(
            "Donuk Kart", "credit_card", credit_limit=10000
        )
        AccountService.set_card_frozen(card_id, True)

        # Yeni bir servis okuması (uygulama yeniden çizimi/yeniden açılışıyla
        # aynı kalıcı DB yolu) state'i korumalı.
        self.assertTrue(AccountService.get_account(card_id)["is_frozen"])
        for transaction_type, installments in (
            ("expense", None),
            ("income", None),
            ("expense", 3),
        ):
            with self.subTest(transaction_type=transaction_type,
                              installments=installments):
                with self.assertRaisesRegex(ValueError, "donduruldu"):
                    TransactionService.add_transaction(
                        card_id, 100, transaction_type, "Test", "Donuk işlem",
                        installments=installments,
                    )

        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)

        AccountService.set_card_frozen(card_id, False)
        TransactionService.add_transaction(
            card_id, 100, "expense", "Test", "Çözülmüş kart"
        )
        self.assertEqual(AccountService.get_account(card_id)["debt"], 100.0)

    def test_frozen_checking_account_is_also_blocked(self):
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        account_id = AccountService.create_account(
            "Donuk Vadesiz", "checking", initial_balance=1000
        )
        AccountService.set_card_frozen(account_id, True)
        with self.assertRaisesRegex(ValueError, "donduruldu"):
            TransactionService.add_transaction(
                account_id, 100, "expense", "Test", "Donuk vadesiz"
            )

    def test_online_preference_persists_but_does_not_block_unclassified_spending(self):
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        card_id = AccountService.create_account(
            "Online Tercih", "credit_card", credit_limit=1000
        )
        AccountService.set_online_payments(card_id, False)
        self.assertFalse(
            AccountService.get_account(card_id)["online_payments_enabled"]
        )

        # İşlem şemasında online/offline alanı yok: tercih dürüstçe saklanır,
        # sıradan harcamayı güvenlik kontrolüymüş gibi engellemez.
        TransactionService.add_transaction(
            card_id, 100, "expense", "Market", "Fiziksel POS"
        )
        self.assertEqual(AccountService.get_account(card_id)["debt"], 100.0)

    def test_frozen_card_can_still_receive_debt_payment(self):
        from services.account_service import AccountService

        checking_id = AccountService.create_account(
            "Ödeme Hesabı", "checking", initial_balance=1000
        )
        card_id = AccountService.create_account(
            "Borçlu Kart", "credit_card",
            initial_balance=500, credit_limit=5000,
        )
        AccountService.set_card_frozen(card_id, True)
        AccountService.pay_credit_card_debt(card_id, checking_id, 200)

        self.assertTrue(AccountService.get_account(card_id)["is_frozen"])
        self.assertEqual(AccountService.get_account(card_id)["debt"], 300.0)
        self.assertEqual(AccountService.get_account(checking_id)["balance"], 800.0)

    def test_frozen_account_blocks_due_recurring_without_advancing_due_date(self):
        from database.db import (
            get_active_recurring_payments, insert_recurring_payment,
            process_due_recurring_payment,
        )
        from services.account_service import AccountService

        account_id = AccountService.create_account(
            "Abonelik Kartı", "credit_card", credit_limit=5000
        )
        insert_recurring_payment(
            "QA Abonelik", 100, "Dijital Abonelik", "monthly",
            "2026-07-15", True, account_id=account_id, recurrence_day=15,
        )
        payment = get_active_recurring_payments()[0]
        AccountService.set_card_frozen(account_id, True)

        with self.assertRaisesRegex(ValueError, "donduruldu"):
            process_due_recurring_payment(payment)

        persisted = get_active_recurring_payments()[0]
        self.assertEqual(persisted["next_due_date"], "2026-07-15")
        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
