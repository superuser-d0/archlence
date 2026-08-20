"""İleri tarihli (pending) işlem akışının testleri.

Spec: "Sistem tam bir bankacılık uygulaması gibi, o tarih gelmeden bakiyeyi
yansıtmamalıdır." Yani ileri tarihli bir kayıt girildiğinde bakiye değişmez,
vadesi geldiğinde settle_due_transactions onu bakiyeye işler.

İzolasyon deseni tests/test_insights_service.py ile aynı: geçici DB dosyası,
database.db.DB_NAME patch'lenir (get_connection çağrı anında okur).
"""
import os
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class PendingTransactionTestCase(unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()

        from database.init_db import initialize_database
        initialize_database()

        # init_db artık varsayılan hesap seed'lemiyor (spec 1.4: kullanıcının
        # eklemediği 2500 TL nakit görünmesin), o yüzden test kendi hesabını kurar.
        from database.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO accounts(name, type, balance, account_type,"
                " credit_limit, statement_date) VALUES(?,?,?,?,?,?)",
                ("Test Vadesiz", "cash", 0.0, "checking", 0, None),
            )
            self.account_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    # ─── Yardımcılar ─────────────────────────────────────────────────────────

    def _set_balance(self, amount):
        from database.db import get_connection
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE accounts SET balance = ? WHERE id = ?",
                (float(amount), self.account_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _balance(self):
        from database.db import get_connection
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT balance FROM accounts WHERE id = ?", (self.account_id,)
            ).fetchone()
        finally:
            conn.close()
        return row["balance"]

    def _add(self, amount, tx_type, day_offset, category="Maaş"):
        """day_offset gün sonrası (negatif = geçmiş) tarihli işlem ekler."""
        from services.transaction_service import TransactionService
        when = (date.today() + timedelta(days=day_offset)).isoformat()
        TransactionService.add_transaction(
            account_id=self.account_id,
            amount=amount,
            transaction_type=tx_type,
            category=category,
            description=f"{category} testi",
            transaction_date=f"{when} 09:00:00",
            enforce_credit_limit=False,
        )

    def _status_counts(self):
        from database.db import get_connection
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM transactions GROUP BY status"
            ).fetchall()
        finally:
            conn.close()
        return {r["status"]: r["n"] for r in rows}

    # ─── Testler ─────────────────────────────────────────────────────────────

    def test_future_income_does_not_touch_balance(self):
        """Spec senaryosu: ayın 4'ünde ayın 5'i tarihli maaş girilirse bakiye 0 kalır."""
        self._add(40000.0, "income", day_offset=1)
        self.assertAlmostEqual(self._balance(), 0.0, places=2)
        self.assertEqual(self._status_counts().get("pending"), 1)

    def test_today_transaction_applies_immediately(self):
        self._add(1000.0, "income", day_offset=0)
        self.assertAlmostEqual(self._balance(), 1000.0, places=2)
        self.assertEqual(self._status_counts().get("completed"), 1)

    def test_settle_applies_balance_when_date_arrives(self):
        """Vade geldiğinde bakiye işlenir ve kayıt 'completed' olur."""
        from services.transaction_service import TransactionService
        self._add(40000.0, "income", day_offset=2)
        self.assertAlmostEqual(self._balance(), 0.0, places=2)

        future = (date.today() + timedelta(days=2)).isoformat()
        settled = TransactionService.settle_due_transactions(today=future)

        self.assertEqual(settled, 1)
        self.assertAlmostEqual(self._balance(), 40000.0, places=2)
        self.assertEqual(self._status_counts().get("completed"), 1)
        self.assertIsNone(self._status_counts().get("pending"))

    def test_settle_is_idempotent(self):
        """Aynı gün tekrar çağrılmak bakiyeyi iki kez artırmamalı."""
        from services.transaction_service import TransactionService
        self._add(500.0, "income", day_offset=1)
        future = (date.today() + timedelta(days=1)).isoformat()

        TransactionService.settle_due_transactions(today=future)
        second_pass = TransactionService.settle_due_transactions(today=future)

        self.assertEqual(second_pass, 0)
        self.assertAlmostEqual(self._balance(), 500.0, places=2)

    def test_settle_leaves_not_yet_due_alone(self):
        from services.transaction_service import TransactionService
        self._add(500.0, "income", day_offset=10)
        settled = TransactionService.settle_due_transactions()
        self.assertEqual(settled, 0)
        self.assertAlmostEqual(self._balance(), 0.0, places=2)

    def test_expense_settles_as_deduction(self):
        """Fatura günü gelince bakiyeden düşülür (spec: ayın 7'si senaryosu)."""
        from services.transaction_service import TransactionService
        self._set_balance(40000.0)
        self._add(1500.0, "expense", day_offset=3, category="Elektrik")

        self.assertAlmostEqual(self._balance(), 40000.0, places=2)
        future = (date.today() + timedelta(days=3)).isoformat()
        TransactionService.settle_due_transactions(today=future)
        self.assertAlmostEqual(self._balance(), 38500.0, places=2)

    def test_pending_excluded_from_period_metrics(self):
        """Bekleyen işlem bakiyeye girmediği gibi dashboard metriklerine de girmez."""
        from services.transaction_service import TransactionService
        self._add(1000.0, "income", day_offset=0)
        self._add(40000.0, "income", day_offset=1)

        rows = TransactionService.get_transactions_by_period("Hayat Boyu")
        total = sum(r["amount"] for r in rows if r["type"] == "income")
        self.assertAlmostEqual(total, 1000.0, places=2)

    def test_pending_listed_for_panel(self):
        from services.transaction_service import TransactionService
        self._add(40000.0, "income", day_offset=5)
        pending = TransactionService.get_pending_transactions()

        self.assertEqual(len(pending), 1)
        self.assertAlmostEqual(pending[0]["amount"], 40000.0, places=2)
        self.assertEqual(
            pending[0]["execution_date"],
            (date.today() + timedelta(days=5)).isoformat(),
        )

    def test_cancel_pending_removes_without_touching_balance(self):
        from services.transaction_service import TransactionService
        self._add(40000.0, "income", day_offset=5)
        pending_id = TransactionService.get_pending_transactions()[0]["id"]

        self.assertTrue(TransactionService.cancel_pending_transaction(pending_id))
        self.assertEqual(TransactionService.get_pending_transactions(), [])
        self.assertAlmostEqual(self._balance(), 0.0, places=2)

    def test_cancel_refuses_completed_transaction(self):
        """Bakiyeye işlenmiş kayıt bu yoldan silinemez (bakiye/defter ayrışmasın)."""
        from services.transaction_service import TransactionService
        self._add(1000.0, "income", day_offset=0)
        from database.db import get_connection
        conn = get_connection()
        try:
            tx_id = conn.execute("SELECT id FROM transactions").fetchone()["id"]
        finally:
            conn.close()

        self.assertFalse(TransactionService.cancel_pending_transaction(tx_id))
        self.assertAlmostEqual(self._balance(), 1000.0, places=2)

    def test_reschedule_to_today_makes_it_settle(self):
        from services.transaction_service import TransactionService
        self._add(2500.0, "income", day_offset=20)
        pending_id = TransactionService.get_pending_transactions()[0]["id"]

        self.assertTrue(TransactionService.reschedule_pending_transaction(
            pending_id, date.today().isoformat()))
        self.assertEqual(TransactionService.settle_due_transactions(), 1)
        self.assertAlmostEqual(self._balance(), 2500.0, places=2)

    def test_reschedule_keeps_full_timestamp_format(self):
        """transaction_date tarih-only yazılmamalı.

        ui/charts.py zaman kovalarını kurarken tam zaman damgası bekliyor;
        tek bir tarih-only satır TÜM zaman grafiğinin sessizce çizilmemesine
        yol açıyordu.
        """
        from datetime import datetime
        from services.transaction_service import TransactionService
        from database.db import get_connection
        self._add(300.0, "income", day_offset=4)
        pending_id = TransactionService.get_pending_transactions()[0]["id"]
        target = (date.today() + timedelta(days=12)).isoformat()

        TransactionService.reschedule_pending_transaction(pending_id, target)

        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT transaction_date, execution_date FROM transactions"
                " WHERE id = ?", (pending_id,)
            ).fetchone()
        finally:
            conn.close()

        for column in ("transaction_date", "execution_date"):
            with self.subTest(column=column):
                # Hata fırlatmadan tam biçimde parse edilebilmeli.
                datetime.strptime(row[column], "%Y-%m-%d %H:%M:%S")
                self.assertTrue(row[column].startswith(target))

    def test_settle_writes_balance_event_ledger(self):
        """Bakiyeye dokunan her akış gibi settle da defter satırı yazmalı."""
        from services.transaction_service import TransactionService
        from database.db import get_connection
        self._add(700.0, "income", day_offset=1)
        future = (date.today() + timedelta(days=1)).isoformat()
        TransactionService.settle_due_transactions(today=future)

        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT delta, source FROM balance_events"
                " WHERE entity_type = 'account' AND delta = 700.0"
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "transaction")

    def test_one_unsettleable_row_does_not_abort_the_rest(self):
        """Yerleşemeyen bir satır KALAN vadesi gelmiş işlemleri iptal etmemeli.

        Bu dalın daha önce hiç testi yoktu ve hiç LOG'u da yoktu: hesabı
        bulunamayan bir bekleyen işlem sessizce geri alınıyordu, yani
        kullanıcının kirası/maaşı hiç işlenmeden geçtiğinde ortada tek bir iz
        kalmıyordu. Handler `except Exception` iken de bu testin geçmesi
        beklenir — asıl doğruladığı şey, DARALTILMIŞ kümenin
        (`sqlite3.Error, ValueError, ArchlenceError`) gerçekten olan hatayı
        hâlâ yakaladığı: `adjust_account_balance` var olmayan hesap için
        ValueError fırlatır ve bu istisna döngüyü ÖLDÜRMEMELİ.
        """
        from services.transaction_service import TransactionService

        self._add(500.0, "income", day_offset=1)

        # Vadesi gelmiş ama hesabı olmayan ikinci bir kayıt.
        #
        # ÇIPLAK `sqlite3.connect` KULLANILIYOR, `get_connection()` DEĞİL — ve
        # bu bilinçli. `get_connection()` artık `PRAGMA foreign_keys=ON` ile
        # geliyor, yani böyle bir satırı bugün YAZAMIYOR (kısıt tam da bunu
        # engellemek için). Testin konusu ise satırın nasıl oluştuğu değil,
        # ZATEN VAR OLAN böyle bir satırın döngüyü öldürmemesi: zorlama
        # kapalıyken yazılmış eski profillerde bu satırlar duruyor olabilir.
        # Fixture, o eski sürümün yaptığını birebir taklit ediyor.
        import sqlite3 as _sqlite3
        from database.db import DB_NAME, SECRET_KEY
        from utils.crypto import encrypt
        when = (date.today() + timedelta(days=1)).isoformat()
        conn = _sqlite3.connect(DB_NAME)
        try:
            conn.execute(
                "INSERT INTO transactions(amount, type, category, description,"
                " transaction_date, execution_date, status, account_id)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (encrypt("50.00", SECRET_KEY), "expense", "Market",
                 encrypt("yetim kayıt", SECRET_KEY), f"{when} 09:00:00",
                 f"{when} 09:00:00", "pending", 999999),
            )
            conn.commit()
        finally:
            conn.close()

        settled = TransactionService.settle_due_transactions(today=when)

        # Sağlıklı kayıt yerleşti, yetim kayıt pending kaldı, istisna kaçmadı.
        self.assertEqual(settled, 1)
        self.assertAlmostEqual(self._balance(), 500.0, places=2)
        self.assertEqual(self._status_counts().get("completed"), 1)
        self.assertEqual(self._status_counts().get("pending"), 1)


if __name__ == "__main__":
    unittest.main()
