"""Çoklu hesap / kredi kartı mantığının testleri.

Kullanıcının istediği kabul senaryosu buradadır (test_credit_card_scenario):
10.000 TL limitli bir kart eklenir, karttan 500 TL market harcaması yapılır ve
net servetin tam olarak 500 TL düştüğü doğrulanır.

Testler geçici bir veritabanı dosyası üzerinde çalışır — kullanıcının gerçek
finance.db'sine dokunulmaz.
"""
import os
import sqlite3
import tempfile
import unittest
from unittest import mock


class AccountServiceTestCase(unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        # db.DB_NAME modül seviyesinde okunuyor; get_connection çağrı anında
        # okuduğu için patch yeterli.
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()

        from database.init_db import initialize_database
        initialize_database()

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def _raw_accounts(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute("SELECT * FROM accounts")]
        conn.close()
        return rows

    # ─── Şema / migration ────────────────────────────────────────────────────

    def test_schema_has_new_columns(self):
        cols = set(self._raw_accounts()[0].keys())
        self.assertIn("account_type", cols)
        self.assertIn("credit_limit", cols)
        self.assertIn("statement_date", cols)

    def test_migration_backfills_existing_rows(self):
        """Eski şemayla (4 sütun) oluşturulmuş bir DB migrate edilince hiçbir
        hesap türsüz kalmamalı ve eski 'credit' hesabı kredi kartı olmalı."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("DROP TABLE accounts")
        conn.execute("""
            CREATE TABLE accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                balance REAL DEFAULT 0
            )
        """)
        conn.executemany(
            "INSERT INTO accounts(name,type,balance) VALUES(?,?,?)",
            [("Eski Nakit", "cash", 1000), ("Eski Kart", "credit", -750)],
        )
        conn.commit()
        conn.close()

        from database.init_db import initialize_database
        initialize_database()

        from services.account_service import AccountService
        by_name = {a["name"]: a for a in AccountService.get_accounts()}
        self.assertEqual(by_name["Eski Nakit"]["account_type"], "checking")
        self.assertEqual(by_name["Eski Kart"]["account_type"], "credit_card")
        # Bakiyeler migration sırasında bozulmamalı
        self.assertEqual(by_name["Eski Nakit"]["balance"], 1000.0)
        self.assertEqual(by_name["Eski Kart"]["debt"], 750.0)

    # ─── Hesap oluşturma ─────────────────────────────────────────────────────

    def test_create_credit_card_stores_debt_as_negative_balance(self):
        from services.account_service import AccountService
        acc_id = AccountService.create_account(
            "Test Kart", "credit_card", initial_balance=1500, credit_limit=10000
        )
        raw = [r for r in self._raw_accounts() if r["id"] == acc_id][0]
        self.assertEqual(raw["balance"], -1500.0)
        self.assertEqual(raw["credit_limit"], 10000.0)

        acc = AccountService.get_account(acc_id)
        self.assertEqual(acc["debt"], 1500.0)
        self.assertEqual(acc["available_limit"], 8500.0)

    def test_create_account_validation(self):
        from services.account_service import AccountService
        with self.assertRaises(ValueError):
            AccountService.create_account("", "checking")
        with self.assertRaises(ValueError):
            AccountService.create_account("Kart", "credit_card", credit_limit=0)
        with self.assertRaises(ValueError):
            AccountService.create_account(
                "Kart", "credit_card", initial_balance=200, credit_limit=100
            )
        with self.assertRaises(ValueError):
            AccountService.create_account(
                "Kart", "credit_card", credit_limit=1000, statement_date=45
            )

    def test_checking_account_ignores_card_fields(self):
        from services.account_service import AccountService
        acc_id = AccountService.create_account(
            "Vadesiz", "checking", initial_balance=2000,
            credit_limit=5000, statement_date=10,
        )
        acc = AccountService.get_account(acc_id)
        self.assertEqual(acc["balance"], 2000.0)
        self.assertEqual(acc["credit_limit"], 0.0)
        self.assertIsNone(acc["statement_date"])

    # ─── Kabul senaryosu ─────────────────────────────────────────────────────

    def test_credit_card_scenario(self):
        """10.000 TL limitli kart + 500 TL market harcaması → net servet -500."""
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        before = AccountService.get_net_worth()

        card_id = AccountService.create_account(
            "Bonus Kart", "credit_card",
            initial_balance=0, credit_limit=10000, statement_date=15,
        )

        # Yeni kartın borcu 0 olduğu için net servet değişmemeli
        after_add = AccountService.get_net_worth()
        self.assertEqual(after_add["net"], before["net"])

        card = AccountService.get_account(card_id)
        self.assertEqual(card["debt"], 0.0)
        self.assertEqual(card["available_limit"], 10000.0)

        TransactionService.add_transaction(
            account_id=card_id, amount=500.0, transaction_type="expense",
            category="Süpermarket", description="Market alışverişi",
        )

        card = AccountService.get_account(card_id)
        self.assertEqual(card["debt"], 500.0, "Karttan gider borcu ARTIRMALI")
        self.assertEqual(card["available_limit"], 9500.0)

        after_spend = AccountService.get_net_worth()
        self.assertEqual(after_spend["card_debt"], before["card_debt"] + 500.0)
        self.assertEqual(after_spend["cash"], before["cash"],
                         "Kart harcaması nakit bakiyeye dokunmamalı")
        self.assertEqual(after_spend["net"], round(before["net"] - 500.0, 2),
                         "Net servet kart borcu kadar DÜŞMELİ")

    def test_checking_expense_reduces_balance(self):
        """Zıt matematiğin diğer ucu: vadesizden gider bakiyeyi düşürür."""
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        acc_id = AccountService.create_account("Vadesiz", "checking", initial_balance=1000)
        TransactionService.add_transaction(
            account_id=acc_id, amount=300.0, transaction_type="expense",
            category="Süpermarket", description="Market",
        )
        self.assertEqual(AccountService.get_account(acc_id)["balance"], 700.0)

    def test_card_payment_reduces_debt(self):
        """Karta ödeme (income) borcu azaltır ve net serveti yükseltir."""
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        card_id = AccountService.create_account(
            "Kart", "credit_card", initial_balance=2000, credit_limit=10000
        )
        net_before = AccountService.get_net_worth()["net"]

        TransactionService.add_transaction(
            account_id=card_id, amount=800.0, transaction_type="income",
            category="Borç Ödeme", description="Kart ödemesi",
        )

        self.assertEqual(AccountService.get_account(card_id)["debt"], 1200.0)
        self.assertEqual(AccountService.get_net_worth()["net"], round(net_before + 800.0, 2))

    def test_debt_payment_moves_cash_and_card_atomically(self):
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        source_id = AccountService.create_account("Maaş", "checking", initial_balance=5000)
        card_id = AccountService.create_account(
            "Kart", "credit_card", initial_balance=2400, credit_limit=3000
        )

        AccountService.pay_credit_card_debt(card_id, source_id, 900)

        self.assertEqual(AccountService.get_account(source_id)["balance"], 4100.0)
        card = AccountService.get_account(card_id)
        self.assertEqual(card["debt"], 1500.0)
        self.assertEqual(card["available_limit"], 1500.0)

        statement = TransactionService.get_recent_for_account(card_id, limit=None)
        self.assertEqual(len(statement), 1)
        self.assertEqual(statement[0]["type"], "payment")
        self.assertEqual(statement[0]["amount"], 900.0)

    def test_debt_payment_cannot_exceed_debt(self):
        from services.account_service import AccountService

        source_id = AccountService.create_account("Maaş", "checking", initial_balance=5000)
        card_id = AccountService.create_account(
            "Kart", "credit_card", initial_balance=500, credit_limit=3000
        )

        with self.assertRaisesRegex(ValueError, "mevcut borcu aşamaz"):
            AccountService.pay_credit_card_debt(card_id, source_id, 501)

        self.assertEqual(AccountService.get_account(source_id)["balance"], 5000.0)
        self.assertEqual(AccountService.get_account(card_id)["debt"], 500.0)

    def test_debt_payment_rejects_card_without_debt(self):
        from services.account_service import AccountService

        source_id = AccountService.create_account("Maaş", "checking", initial_balance=5000)
        card_id = AccountService.create_account("Kart", "credit_card", credit_limit=3000)

        with self.assertRaisesRegex(ValueError, "ödenecek borç bulunmuyor"):
            AccountService.pay_credit_card_debt(card_id, source_id, 100)

        self.assertEqual(AccountService.get_account(source_id)["balance"], 5000.0)
        self.assertEqual(AccountService.get_account(card_id)["balance"], 0.0)

    def test_delete_credit_card_removes_only_its_data(self):
        from database.db import get_connection
        from services.account_service import AccountService
        from services.transaction_service import TransactionService
        from utils.crypto import encrypt
        from database.db import SECRET_KEY

        deleted_id = AccountService.create_account(
            "Silinecek", "credit_card", initial_balance=200, credit_limit=3000
        )
        kept_id = AccountService.create_account(
            "Kalacak", "credit_card", initial_balance=100, credit_limit=3000
        )
        TransactionService.add_transaction(
            deleted_id, 50, "expense", "Test", "Silinecek hareket"
        )
        TransactionService.add_transaction(
            kept_id, 25, "expense", "Test", "Kalacak hareket"
        )

        conn = get_connection()
        conn.execute(
            "INSERT INTO recurring_payments"
            " (name, amount, category, frequency, next_due_date, auto_deduct, is_active, account_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (encrypt("Abonelik", SECRET_KEY), encrypt("10", SECRET_KEY), "Test",
             "monthly", "2026-08-01", 1, 1, deleted_id),
        )
        conn.commit()
        conn.close()

        AccountService.delete_credit_card(deleted_id)

        self.assertIsNone(AccountService.get_account(deleted_id))
        self.assertIsNotNone(AccountService.get_account(kept_id))
        self.assertEqual(len(TransactionService.get_recent_for_account(deleted_id, None)), 0)
        self.assertEqual(len(TransactionService.get_recent_for_account(kept_id, None)), 1)

        conn = get_connection()
        recurring = conn.execute(
            "SELECT id FROM recurring_payments WHERE account_id = ?", (deleted_id,)
        ).fetchone()
        events = conn.execute(
            "SELECT COUNT(*) FROM balance_events WHERE entity_type = 'account' AND entity_id = ?",
            (deleted_id,),
        ).fetchone()[0]
        conn.close()
        self.assertIsNone(recurring)
        self.assertEqual(events, 0)

    # ─── Limit kontrolü ──────────────────────────────────────────────────────

    def test_expense_over_limit_is_rejected(self):
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        card_id = AccountService.create_account(
            "Dar Kart", "credit_card", initial_balance=900, credit_limit=1000
        )
        with self.assertRaises(ValueError):
            TransactionService.add_transaction(
                account_id=card_id, amount=250.0, transaction_type="expense",
                category="Süpermarket", description="Limit aşan harcama",
            )
        # Reddedilen işlem borcu değiştirmemeli
        self.assertEqual(AccountService.get_account(card_id)["debt"], 900.0)

    def test_import_bypasses_limit_check(self):
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        card_id = AccountService.create_account(
            "Dar Kart", "credit_card", initial_balance=900, credit_limit=1000
        )
        TransactionService.add_transaction(
            account_id=card_id, amount=250.0, transaction_type="expense",
            category="Süpermarket", description="Geçmiş kayıt",
            enforce_credit_limit=False,
        )
        self.assertEqual(AccountService.get_account(card_id)["debt"], 1150.0)

    def test_net_worth_matches_sum_of_balances(self):
        """İşaretli konvansiyonun değişmezi: net servet == SUM(balance).

        Bu kırılırsa accounts.balance'a dokunan bir yer işaret kuralını bozmuş
        demektir (bkz. db.adjust_account_balance docstring'i)."""
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        AccountService.create_account("Ek Vadesiz", "checking", initial_balance=4000)
        card_id = AccountService.create_account(
            "Ek Kart", "credit_card", initial_balance=1200, credit_limit=10000
        )
        TransactionService.add_transaction(
            account_id=card_id, amount=300.0, transaction_type="expense",
            category="Süpermarket", description="Market",
        )

        conn = sqlite3.connect(self.db_path)
        raw_sum = conn.execute("SELECT SUM(balance) FROM accounts").fetchone()[0]
        conn.close()

        self.assertEqual(AccountService.get_net_worth()["net"], round(raw_sum, 2))

    def test_migrated_card_without_limit_is_not_blocked(self):
        """Migration'dan gelen kartlar credit_limit=0 ile gelir; bu 'limit
        belirlenmemiş' demektir, harcama engellenmemeli."""
        import sqlite3 as _sq
        conn = _sq.connect(self.db_path)
        conn.execute("UPDATE accounts SET credit_limit = 0 WHERE account_type = 'credit_card'")
        conn.commit()
        conn.close()

        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        card = [a for a in AccountService.get_accounts()
                if a["account_type"] == "credit_card"][0]
        TransactionService.add_transaction(
            account_id=card["id"], amount=750.0, transaction_type="expense",
            category="Süpermarket", description="Limitsiz kart harcaması",
        )
        self.assertEqual(AccountService.get_account(card["id"])["debt"],
                         round(card["debt"] + 750.0, 2))


if __name__ == "__main__":
    unittest.main()
