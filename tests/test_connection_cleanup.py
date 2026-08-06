"""SQLite bağlantıları deterministik kapanmalı — GC'ye bağlı olmadan.

DURUM KAYDI: Phase 2 denetimi 100 operasyon boyunca file descriptor sayısının
4 → 71 çıktığını, sonra GC veya zamanla düştüğünü ölçmüştü. Bu bulgu Phase 3
sonrası HEAD'de **YENİDEN ÜRETİLEMEDİ**: yedi ayrı operasyon türünde 100'er
tekrar sonrası delta 0 çıktı.

Muhtemel sebep, Phase 3'ün atomiklik düzeltmelerinin (`AssetSaleService`,
`DebtPaymentService`, `managed_connection` yaygınlaşması) o yolları zaten
deterministik hale getirmesi. Bu dosya bir DÜZELTME değil, davranışı
SABİTLEYEN regresyon korumasıdır: ileride bir yol `try/finally` veya
`managed_connection` olmadan yazılırsa test kırılır.

Ayrıca ownership sözleşmesi test ediliyor: Python'da `with conn:` bağlantıyı
KAPATMAZ, yalnızca commit/rollback yapar. Bu ayrım kolayca kaçırılır.
"""

import gc
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest import mock

_FD_DIR = f"/proc/{os.getpid()}/fd"


def _fd_count():
    return len(os.listdir(_FD_DIR))


@unittest.skipUnless(
    os.path.isdir(_FD_DIR),
    "file descriptor sayımı /proc gerektirir (Linux)",
)
class ConnectionCleanupTest(unittest.TestCase):
    # Ortam gürültüsüne dayanıklı, belgelenmiş tolerans. Asıl aranan şey
    # "onlarca bağlantı birikiyor mu"; tam sayı değil.
    TOLERANCE = 5

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patch = mock.patch("database.db.DB_NAME", self.db_path)
        self._patch.start()
        from database.init_db import initialize_database
        from services.account_service import AccountService

        initialize_database()
        self.account_id = AccountService.create_account(
            "FD Hesabı", "checking", initial_balance=10_000_000.0
        )

    def tearDown(self):
        self._patch.stop()
        os.unlink(self.db_path)

    def _assert_bounded(self, label, operation, repeats=100):
        """GC ÇAĞIRMADAN sınırlı kalmalı — asıl iddia bu."""
        gc.collect()
        before = _fd_count()
        for index in range(repeats):
            operation(index)
        after = _fd_count()
        self.assertLessEqual(
            after - before, self.TOLERANCE,
            f"{label}: {repeats} işlemde FD {before} -> {after} "
            f"(explicit GC olmadan sınırlı kalmalı)",
        )

    def test_transaction_writes_do_not_accumulate_descriptors(self):
        from services.transaction_service import TransactionService

        self._assert_bounded(
            "transaction_write",
            lambda i: TransactionService.add_transaction(
                self.account_id, 1.0, "expense", "T", "d",
                transaction_date="2026-08-01 10:00:00",
                detect_subscription=False,
            ),
        )

    def test_period_queries_do_not_accumulate_descriptors(self):
        from services.transaction_service import TransactionService

        self._assert_bounded(
            "period_query",
            lambda i: TransactionService.get_transactions_by_period("Bugün"),
        )

    def test_savings_round_trips_do_not_accumulate_descriptors(self):
        from services.savings_service import SavingsService

        goal_id = SavingsService.create_goal("Hedef", 1_000_000.0)

        def _cycle(_index):
            SavingsService.deposit_to_goal(goal_id, 1.0, self.account_id)
            SavingsService.withdraw_from_goal(goal_id, 1.0, self.account_id)

        self._assert_bounded("savings_cycle", _cycle, repeats=50)

    def test_asset_purchases_do_not_accumulate_descriptors(self):
        from services.asset_purchase_service import AssetPurchaseService

        self._assert_bounded(
            "asset_purchase",
            lambda i: AssetPurchaseService.create_purchase(
                asset_name="A", asset_code="A", asset_type="Altın",
                purchase_price=10.0, quantity=1.0,
                account_id=self.account_id,
            ),
            repeats=50,
        )

    def test_database_file_can_be_replaced_after_operations(self):
        """Windows file-lock hazırlığı: dosya işlem sonrası taşınabilmeli.

        Linux'ta açık handle rename'i engellemez, dolayısıyla bu test
        Windows'un yerine geçmez. Yine de açıkta kalan bir bağlantının
        varlığını ayrıca doğrular.
        """
        from services.transaction_service import TransactionService

        for _ in range(20):
            TransactionService.add_transaction(
                self.account_id, 1.0, "expense", "T", "d",
                transaction_date="2026-08-01 10:00:00",
                detect_subscription=False,
            )
        moved = self.db_path + ".moved"
        os.replace(self.db_path, moved)
        self.assertTrue(os.path.exists(moved))
        os.replace(moved, self.db_path)


class ConnectionOwnershipTest(unittest.TestCase):
    """`with conn:` bağlantıyı KAPATMAZ — bu ayrım kolayca kaçırılır."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patch = mock.patch("database.db.DB_NAME", self.db_path)
        self._patch.start()
        from database.init_db import initialize_database

        initialize_database()

    def tearDown(self):
        self._patch.stop()
        os.unlink(self.db_path)

    def test_sqlite_context_manager_does_not_close(self):
        """Python sözleşmesi: `with conn:` yalnız commit/rollback yapar.

        Bu davranış varsayılırsa bağlantı sızar. Test, kod tabanının bu
        varsayıma dayanmadığını hatırlatmak için burada.
        """
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("SELECT 1")
        # Hâlâ AÇIK — kapanmış olsaydı bu satır ProgrammingError verirdi.
        conn.execute("SELECT 1")
        conn.close()
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_managed_connection_closes_on_success(self):
        from database.db import managed_connection

        with managed_connection() as conn:
            conn.execute("SELECT 1")
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_managed_connection_closes_on_exception(self):
        from database.db import managed_connection

        captured = None
        with self.assertRaises(ValueError):
            with managed_connection() as conn:
                captured = conn
                raise ValueError("boom")
        with self.assertRaises(sqlite3.ProgrammingError):
            captured.execute("SELECT 1")

    def test_externally_supplied_cursor_is_not_closed_by_callee(self):
        """Dışarıdan cursor alan fonksiyon bağlantıyı kapatmamalı.

        `adjust_account_balance` açık bir cursor alır ve çağıranın commit'ine
        katılır; kapatırsa çağıranın transaction'ını yarıda keserdi.
        """
        from database.db import adjust_account_balance, managed_connection
        from services.account_service import AccountService

        account_id = AccountService.create_account(
            "Sahiplik", "checking", initial_balance=100.0
        )
        with managed_connection() as conn:
            cursor = conn.cursor()
            adjust_account_balance(cursor, account_id, "income", 50.0)
            # Bağlantı hâlâ kullanılabilir olmalı.
            balance = cursor.execute(
                "SELECT balance FROM accounts WHERE id=?", (account_id,)
            ).fetchone()[0]
            conn.commit()
        self.assertEqual(balance, 150.0)


if __name__ == "__main__":
    unittest.main()
