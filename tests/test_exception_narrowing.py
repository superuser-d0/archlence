"""docs/ROADMAP.md Faz 2 "except ayrımı" — services/database/utils
katmanındaki decrypt-bitişik `except Exception` bloklarının `except
(ValueError, TypeError)`'a daraltılması.

DAVRANIŞ BİLEREK DEĞİŞMEDİ: gerçek bozuk/kurcalanmış veri hâlâ aynı zararsız
yerine geçen değere düşüyor (0.0, "Bilinmeyen ...", boş string). Değişen tek
şey: artık yalnızca decrypt()'in gerçekten üretebileceği hata tipleri
yakalanıyor. Alakasız bir programlama hatası (ör. şema uyuşmazlığından gelen
bir KeyError) bu kapının arkasına gizlenip aynı "bozuk veri" mesajına
karışmıyor — gerçek hatasıyla yükseliyor.

Bu dosya, utils/crypto.py'nin kendi testlerinde (tests/test_crypto.py)
kanıtlanan mekanizmanın çağıran katmanda da (database/db.py) doğru
çalıştığını birkaç temsili fonksiyonla doğrular — 20'den fazla dokunulan
sitenin HER birini ayrı ayrı test etmek yerine, aynı deseni paylaşan
temsili örnekler seçildi.
"""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")


class DecryptFallbackBehaviorPreservedTest(unittest.TestCase):
    """Gerçek bozuk veriyle: davranış eskisiyle birebir aynı kalmalı."""

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

    def test_active_debts_with_corrupted_amount_falls_back_gracefully(self):
        from database.db import insert_debt, get_active_debts
        import sqlite3
        insert_debt("Kredi Kartı Borcu", 5000.0, 500.0, 10)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        debt_id = conn.execute("SELECT id FROM active_debts").fetchone()["id"]
        conn.close()

        self._corrupt_column("active_debts", "total_amount", debt_id)

        debts = get_active_debts()
        self.assertEqual(len(debts), 1)
        self.assertEqual(debts[0]["debt_name"], "Bilinmeyen Borç")
        self.assertEqual(debts[0]["total_amount"], 0.0)

    def test_active_assets_with_corrupted_price_falls_back_gracefully(self):
        from database.db import insert_asset, get_all_assets
        import sqlite3
        insert_asset("Test Hisse", "TEST", "Hisse", "100.0", "5")
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        asset_id = conn.execute("SELECT id FROM active_assets").fetchone()["id"]
        conn.close()

        self._corrupt_column("active_assets", "purchase_price", asset_id)

        assets = get_all_assets()
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["purchase_price"], 0.0)


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
