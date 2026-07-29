"""Takvim görünümü servis katmanının testleri (ay ızgarası + gün detayı).

test_insights_service.py ile aynı izolasyon deseni: geçici DB dosyası,
database.db.DB_NAME patch'lenir. Tarihler `days_ago`/gerçek `datetime.now()`
yerine SABİT ISO tarihleriyle yazılır — test hangi güne denk gelirse gelsin
ay sınırlarının deterministik kalması için.
"""
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fixtures import AccountFixtureMixin


class CalendarServiceTestCase(AccountFixtureMixin, unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()

        from database.init_db import initialize_database
        initialize_database()
        from database.db import DEFAULT_ACCOUNT_ID
        self.account_id = self.create_test_account(
            name="Takvim Testi Vadesiz", balance=10_000.0)
        self.assertEqual(self.account_id, DEFAULT_ACCOUNT_ID)

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def _add_tx_on(self, iso_datetime, amount, tx_type, category, description):
        """Sabit bir tarih-saatte şifreli bir işlem satırı yazar."""
        from database.db import SECRET_KEY
        from utils.crypto import encrypt

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO transactions"
            " (account_id, amount, type, category, description, transaction_date)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (self.account_id, encrypt(str(amount), SECRET_KEY), tx_type, category,
             encrypt(str(description), SECRET_KEY), iso_datetime),
        )
        conn.commit()
        conn.close()

    # ─── get_month_transaction_days ─────────────────────────────────────────

    def test_empty_month_returns_empty_mapping(self):
        from services.calendar_service import get_month_transaction_days

        self.assertEqual(get_month_transaction_days(2026, 3), {})

    def test_counts_transactions_per_day_within_month(self):
        from services.calendar_service import get_month_transaction_days

        self._add_tx_on("2026-03-05 09:00:00", 100, "income", "Maaş", "maaş")
        self._add_tx_on("2026-03-05 18:30:00", 50, "expense", "Market", "market")
        self._add_tx_on("2026-03-17 12:00:00", 20, "expense", "Ulaşım", "otobüs")

        result = get_month_transaction_days(2026, 3)

        self.assertEqual(result, {5: 2, 17: 1})

    def test_different_month_is_not_counted(self):
        from services.calendar_service import get_month_transaction_days

        self._add_tx_on("2026-04-05 09:00:00", 100, "income", "Maaş", "maaş")

        self.assertEqual(get_month_transaction_days(2026, 3), {})
        self.assertEqual(get_month_transaction_days(2026, 4), {5: 1})

    def test_pending_transaction_is_not_counted(self):
        """Vadesi gelmemiş (pending) işlem o günü işaretlememeli — takvim
        yalnızca gerçekleşmiş bakiye hareketlerini gösteriyor olmalı."""
        from services.calendar_service import get_month_transaction_days

        self._add_tx_on("2026-03-05 09:00:00", 100, "income", "Maaş", "maaş")
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE transactions SET status = 'pending'")
        conn.commit()
        conn.close()

        self.assertEqual(get_month_transaction_days(2026, 3), {})

    # ─── get_day_transactions ────────────────────────────────────────────────

    def test_day_with_no_transactions_returns_empty_list(self):
        from services.calendar_service import get_day_transactions
        import datetime

        self.assertEqual(
            get_day_transactions(datetime.date(2026, 3, 5)), [])

    def test_day_transactions_are_decrypted_and_ordered_by_time(self):
        from services.calendar_service import get_day_transactions
        import datetime

        self._add_tx_on("2026-03-05 18:30:00", 50.5, "expense", "Market", "akşam market")
        self._add_tx_on("2026-03-05 09:00:00", 40000, "income", "Maaş", "maaş yattı")
        self._add_tx_on("2026-03-06 09:00:00", 999, "expense", "Diğer", "başka gün")

        items = get_day_transactions(datetime.date(2026, 3, 5))

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["time"], "09:00")
        self.assertEqual(items[0]["type"], "income")
        self.assertEqual(items[0]["category"], "Maaş")
        self.assertEqual(items[0]["amount"], 40000.0)
        self.assertEqual(items[0]["description"], "maaş yattı")
        self.assertEqual(items[1]["time"], "18:30")
        self.assertEqual(items[1]["amount"], 50.5)

    def test_missing_category_falls_back_to_diger(self):
        from services.calendar_service import get_day_transactions
        import datetime

        conn = sqlite3.connect(self.db_path)
        from database.db import SECRET_KEY
        from utils.crypto import encrypt
        conn.execute(
            "INSERT INTO transactions"
            " (account_id, amount, type, category, description, transaction_date)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (self.account_id, encrypt("10", SECRET_KEY), "expense", None,
             encrypt("", SECRET_KEY), "2026-03-05 10:00:00"),
        )
        conn.commit()
        conn.close()

        items = get_day_transactions(datetime.date(2026, 3, 5))
        self.assertEqual(items[0]["category"], "Diğer")


if __name__ == "__main__":
    unittest.main()
