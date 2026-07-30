"""Bozuk finansal alanlar geçerli sıfır/değer gibi gösterilmemelidir."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")


class DecryptFailureIsInvalidDataTest(unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()
        from database.init_db import initialize_database
        initialize_database()

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def _corrupt_column(self, table, column, row_id):
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            f"UPDATE {table} SET {column} = ? WHERE id = ?",
            ("bu-gecerli-sifreli-veri-degil-!!!", row_id),
        )
        conn.commit()
        conn.close()

    def test_active_debts_with_corrupted_amount_invalidates_result(self):
        from database.db import insert_debt, get_active_debts
        from utils.errors import FinancialDataIntegrityError
        import sqlite3
        insert_debt("Kredi Kartı Borcu", 5000.0, 500.0, 10)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        debt_id = conn.execute("SELECT id FROM active_debts").fetchone()["id"]
        conn.close()

        self._corrupt_column("active_debts", "total_amount", debt_id)

        with self.assertRaises(FinancialDataIntegrityError) as raised:
            get_active_debts()
        self.assertEqual(raised.exception.table, "active_debts")
        self.assertEqual(raised.exception.record_id, debt_id)

    def test_active_assets_with_corrupted_price_invalidates_result(self):
        from database.db import insert_asset, get_all_assets
        from utils.errors import FinancialDataIntegrityError
        import sqlite3
        insert_asset("Test Hisse", "TEST", "Hisse", "100.0", "5")
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        asset_id = conn.execute("SELECT id FROM active_assets").fetchone()["id"]
        conn.close()

        self._corrupt_column("active_assets", "purchase_price", asset_id)

        with self.assertRaises(FinancialDataIntegrityError) as raised:
            get_all_assets()
        self.assertEqual(raised.exception.table, "active_assets")
        self.assertEqual(raised.exception.record_id, asset_id)


class UnrelatedBugNowPropagatesTest(unittest.TestCase):
    """Asıl davranış değişikliği: decrypt ile ilgisi olmayan bir hata artık
    '[Şifreli Veri]'/0.0 arkasına gizlenmiyor — gerçek hata olarak yükseliyor."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()
        from database.init_db import initialize_database
        initialize_database()

        from database.db import insert_debt
        insert_debt("Kredi Kartı Borcu", 5000.0, 500.0, 10)

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def test_unrelated_runtime_error_propagates_instead_of_becoming_unknown_debt(self):
        from database import db as db_module

        with mock.patch.object(
            db_module, "decrypt", side_effect=RuntimeError("beklenmedik bug")
        ):
            with self.assertRaises(RuntimeError):
                db_module.get_active_debts()


if __name__ == "__main__":
    unittest.main()
