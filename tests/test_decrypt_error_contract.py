"""`decrypt()` artık raise ediyor — çağıranların sözleşmesi buna uymalı.

ARKA PLAN. PR #22 öncesinde `utils.crypto.decrypt()` her hatayı içeride yutup
bir placeholder dize döndürüyordu. Çağıranlar da o placeholder'ı `float()`'a
verdiklerinde çıkan `ValueError`/`TypeError`'ı yakalayacak şekilde yazılmıştı.

PR #22 `decrypt()`'i fail-closed yaptı: bozuk zarf, kurcalanmış ciphertext ya
da erişilemeyen anahtar artık TİPLİ istisna fırlatıyor
(`IntegrityVerificationError` / `DecryptionError` / `KeyUnavailableError`).
Bunların HİÇBİRİ `ValueError` veya `TypeError` DEĞİL — ölçüldü. Yani çağrı
yerlerindeki eski `except (ValueError, TypeError)` blokları gerçek bir
bozulmada devreye GİRMİYOR, istisna belirsiz bir yere sızıyordu.

Bu dosya iki sözleşmeyi birden sabitler:

  1. KAYIT BAZINDA BOZULMA yakalanır, loglanır ve akış sürer (tek bozuk satır
     tüm listeyi düşürmez).
  2. ANAHTAR ERİŞİLEMEZ ise istisna YUKARI TAŞINIR. Bunu satır bazında yutmak,
     "hiçbir şey çözülemiyor" gibi toplam bir arızayı "hepsi 0,00 TL" /
     "hepsi Bilinmeyen" diye NORMAL VERİ gibi gösterirdi — sessiz ve
     tehlikeli.
"""
import logging
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest import mock

from utils.errors import KeyUnavailableError

# `AEADv1:` önekli ama gövdesi bozuk — decrypt() bunu
# IntegrityVerificationError ile reddeder (ölçüldü).
CORRUPT = "AEADv1:bu-gecerli-bir-zarf-degil"


class _LogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)

    def messages(self):
        return [r.getMessage() for r in self.records]


class DecryptErrorContractTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_patch = mock.patch("database.db.DB_NAME", self.db_path)
        self.db_patch.start()
        from database.init_db import initialize_database
        initialize_database()

        self.capture = _LogCapture()
        logging.getLogger("archlence").addHandler(self.capture)

    def tearDown(self):
        logging.getLogger("archlence").removeHandler(self.capture)
        self.db_patch.stop()
        os.unlink(self.db_path)

    def _sql(self, statement, params=()):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(statement, params)
            conn.commit()

    def _corrupt_row(self, table, columns, extra_columns=None):
        """Verilen tabloya, şifreli kolonları BOZUK olan tek bir satır yazar."""
        values = {column: CORRUPT for column in columns}
        values.update(extra_columns or {})
        names = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        self._sql(
            f"INSERT INTO {table} ({names}) VALUES ({marks})",
            tuple(values.values()),
        )

    # ── 1. Kayıt bazında bozulma: yakala, logla, devam et ────────────────

    def test_corrupt_savings_goal_is_caught_and_logged(self):
        from services.savings_service import SavingsService

        self._corrupt_row(
            "savings_goals", ["goal_name"],
            {"target_amount": 100.0, "current_amount": 0.0},
        )
        goals = SavingsService.get_goals()

        self.assertEqual(len(goals), 1, "bozuk satır listeyi düşürmemeli")
        self.assertEqual(goals[0]["goal_name"], "Bilinmeyen Hedef")
        self.assertTrue(
            any("VERİ BÜTÜNLÜĞÜ" in m for m in self.capture.messages()),
            "bozulma sessiz kalmamalı — eskiden hiç iz bırakmıyordu",
        )

    def test_corrupt_asset_history_row_is_caught_and_logged(self):
        from database.db import get_asset_transaction_history

        self._corrupt_row(
            "transactions", ["amount", "description"],
            {"account_id": 1, "type": "expense", "category": "Varlık Alımı",
             "transaction_date": "2026-08-01 10:00:00"},
        )
        rows = get_asset_transaction_history()

        self.assertEqual(len(rows), 1, "bozuk satır listeyi düşürmemeli")
        self.assertTrue(
            any("VERİ BÜTÜNLÜĞÜ" in m for m in self.capture.messages()))

    def test_corrupt_recurring_payment_is_caught_and_logged(self):
        from database.db import get_active_recurring_payments

        self._corrupt_row(
            "recurring_payments", ["name", "amount"],
            {"frequency": "monthly", "next_due_date": "2026-09-01",
             "transaction_type": "expense", "is_active": 1},
        )
        payments = get_active_recurring_payments()

        self.assertEqual(len(payments), 1)
        self.assertTrue(
            any("VERİ BÜTÜNLÜĞÜ" in m for m in self.capture.messages()))

    def test_corrupt_csv_export_field_is_caught_and_logged(self):
        from services.migration_service import export_all_to_csv

        self._corrupt_row(
            "transactions", ["amount", "description"],
            {"account_id": 1, "type": "expense", "category": "Test",
             "transaction_date": "2026-08-01 10:00:00"},
        )
        export_path = os.path.join(tempfile.mkdtemp(), "export.csv")
        path, count = export_all_to_csv(export_path)

        self.assertEqual(count, 1, "tek bozuk satır dışa aktarımı düşürmemeli")
        self.assertTrue(
            any("VERİ BÜTÜNLÜĞÜ" in m for m in self.capture.messages()))

    # ── 2. Anahtar erişilemez: yut DEĞİL, yukarı taşı ────────────────────

    def _with_unavailable_key(self, module_path):
        """`decrypt()` anahtara erişemiyormuş gibi davransın.

        DİKKAT — `utils.crypto.decrypt` patch'lemek ETKİSİZDİR: çağıran
        modüller `from utils.crypto import decrypt` ile adı KENDİ modül
        ad alanlarına bağlıyor, dolayısıyla kaynaktaki nesneyi değiştirmek
        o bağlamayı etkilemez. Patch, decrypt'i KULLANAN modül üzerinde
        yapılmalı (ilk yazımda bu tuzağa düşülüp test sessizce geçmişti).
        """
        return mock.patch(
            f"{module_path}.decrypt",
            side_effect=KeyUnavailableError("anahtar erişilemiyor"),
        )

    def test_key_unavailable_propagates_from_savings(self):
        from services.savings_service import SavingsService

        self._corrupt_row(
            "savings_goals", ["goal_name"],
            {"target_amount": 100.0, "current_amount": 0.0},
        )
        with self._with_unavailable_key("services.savings_service"):
            with self.assertRaises(KeyUnavailableError):
                SavingsService.get_goals()

    def test_key_unavailable_propagates_from_asset_history(self):
        from database.db import get_asset_transaction_history

        self._corrupt_row(
            "transactions", ["amount", "description"],
            {"account_id": 1, "type": "expense", "category": "Varlık Alımı",
             "transaction_date": "2026-08-01 10:00:00"},
        )
        with self._with_unavailable_key("database.db"):
            with self.assertRaises(KeyUnavailableError):
                get_asset_transaction_history()

    def test_key_unavailable_does_not_produce_a_silently_empty_csv(self):
        """En tehlikeli senaryo: kullanıcı baştan sona BOŞ bir CSV indirip
        verisini kaybettiğini sanır. Hata görünür olmalı."""
        from services.migration_service import export_all_to_csv

        self._corrupt_row(
            "transactions", ["amount", "description"],
            {"account_id": 1, "type": "expense", "category": "Test",
             "transaction_date": "2026-08-01 10:00:00"},
        )
        export_path = os.path.join(tempfile.mkdtemp(), "export.csv")
        with self._with_unavailable_key("services.migration_service"):
            with self.assertRaises(KeyUnavailableError):
                export_all_to_csv(export_path)


if __name__ == "__main__":
    unittest.main()
