"""Migration'ın ŞİFRELİ HER TABLOYU kapsadığını ve içeriği bozmadığını sınar.

`tests/test_crypto_migration_service.py` mekanizmayı doğruluyor (backup-first,
rollback, idempotans) ama tek tablo / iki alan üzerinden. Buradaki testler
KAPSAMA bakıyor:

  1. `ENCRYPTED_FIELDS`'teki her tablo gerçekten taşınıyor mu,
  2. taşınan değerin DÜZ METNİ birebir korunuyor mu (Türkçe karakter, ondalık,
     uzun metin dahil),
  3. envanter sayımı gerçekten var olan legacy alan sayısıyla eşleşiyor mu.

Neden ayrı bir dosya: kapsama bir alan/tablo eklendiğinde (ör. yeni bir
şifreli sütun) kırılması gereken test bu; mekanizma testinin kapsamı
değişmemeli.

Gerçek boyutlu bir veritabanında (1014 kayıt / 2030 alan) elle de
doğrulandı — tamamı 0.8 sn'de taşındı, format ve içerik hatası sıfır.
Buradaki sürüm aynı sözleşmeyi test paketi hızında tutar.
"""
import base64
import functools
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import pad

from services.backup_service import ENCRYPTED_FIELDS
from services.crypto_migration_service import (
    inspect_legacy_encryption,
    migrate_legacy_encryption,
)
from utils.crypto import DEFAULT_PASSWORD, STATIC_SALT, decrypt

_AEAD_PREFIX = "AEADv1:"


_TRICKY_VALUES = [
    "Türkçe karakterli açıklama: şğüöçİ",
    "1234.56",
    "0.00",
    "-987.65",
    "Çok uzun bir açıklama " * 20,
    "İçinde : iki nokta ve AEADv1 kelimesi geçen metin",
]


@functools.lru_cache(maxsize=1)
def _legacy_key():
    """Legacy PBKDF2 anahtarı — 1.000.000 iterasyon, çağrı başına DEĞİL.

    Önbelleklenmeden bu dosya tek başına ~20 sn sürüyordu (test başına
    ~26 alan tohumlanıyor, her biri ayrı bir PBKDF2 türetmesi). Girdi
    sabit olduğu için sonuç da sabit; bir kez hesaplamak yeterli.
    """
    return PBKDF2(DEFAULT_PASSWORD, STATIC_SALT, dkLen=32, count=1_000_000)


def _legacy_encrypt(value):
    """Eski AES-256-CBC formatı — gerçek legacy veri gibi RASTGELE IV ile."""
    iv = os.urandom(16)
    cipher = AES.new(_legacy_key(), AES.MODE_CBC, iv)
    return base64.b64encode(
        iv + cipher.encrypt(pad(str(value).encode("utf-8"), 16))
    ).decode("ascii")


class MigrationCoversEveryEncryptedTableTest(unittest.TestCase):
    PASSPHRASE = "kapsama-testi-parolasi"

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.db_path = root / "finance.db"
        self.key_path = root / "encryption.key"
        self.backup_path = root / "pre-migration.backup"
        self.key = os.urandom(32)
        self.key_path.write_bytes(self.key)

        self.db_patch = mock.patch("database.db.DB_NAME", str(self.db_path))
        self.crypto_key_patch = mock.patch(
            "utils.crypto._get_aead_key", return_value=self.key
        )
        self.db_patch.start()
        self.crypto_key_patch.start()

        from database.init_db import initialize_database

        initialize_database()
        self.expected = self._seed_legacy_rows()

    def tearDown(self):
        self.crypto_key_patch.stop()
        self.db_patch.stop()
        self.tempdir.cleanup()

    def _seed_legacy_rows(self):
        """Her şifreli tabloya legacy CBC satırları yazar.

        `installment_plans` init_db'de YOK — tembel oluşturuluyor
        (bkz. services/transaction_service.py). Test onu açıkça yaratır ki
        migration'ın o tabloyu da gördüğü kanıtlansın.
        """
        expected = {}
        with closing(sqlite3.connect(self.db_path)) as conn:


            conn.execute(
                "INSERT INTO accounts (id, name, type, balance, account_type)"
                " VALUES (1, 'Legacy Hesap', 'checking', 1000, 'checking')"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS installment_plans ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "account_id INTEGER NOT NULL, description TEXT NOT NULL,"
                "total_amount TEXT NOT NULL, monthly_amount TEXT NOT NULL,"
                "total_installments INTEGER NOT NULL,"
                "paid_installments INTEGER NOT NULL DEFAULT 0,"
                "created_at TEXT NOT NULL)"
            )
            inserts = {
                "transactions": (
                    "INSERT INTO transactions (account_id, amount, type, "
                    "category, description, transaction_date) "
                    "VALUES (1, ?, 'expense', 'Test', ?, '2026-08-01')",
                    ("amount", "description"),
                ),
                "active_debts": (
                    "INSERT INTO active_debts (debt_name, total_amount, "
                    "monthly_payment, total_installments, is_active) "
                    "VALUES (?, ?, ?, 12, 1)",
                    ("debt_name", "total_amount", "monthly_payment"),
                ),
                "active_assets": (
                    "INSERT INTO active_assets (asset_name, asset_code, "
                    "asset_type, purchase_price, quantity, purchase_date) "
                    "VALUES ('Test', 'BTC-USD', 'Kripto', ?, ?, '2026-08-01')",
                    ("purchase_price", "quantity"),
                ),
                "recurring_payments": (
                    "INSERT INTO recurring_payments (name, amount, category, "
                    "frequency, next_due_date, is_active) "
                    "VALUES (?, ?, 'Abonelik', 'monthly', '2026-09-01', 1)",
                    ("name", "amount"),
                ),
                "savings_goals": (


                    "INSERT INTO savings_goals (goal_name, target_amount, "
                    "current_amount, status, goal_uid) "
                    "VALUES (?, 1000, 0, 'active', hex(randomblob(16)))",
                    ("goal_name",),
                ),
                "installment_plans": (
                    "INSERT INTO installment_plans (account_id, description, "
                    "total_amount, monthly_amount, total_installments, "
                    "created_at) VALUES (1, ?, ?, ?, 12, '2026-08-01')",
                    ("description", "total_amount", "monthly_amount"),
                ),
                "savings_migration_quarantine": (
                    "INSERT INTO savings_migration_quarantine ("
                    "quarantined_at, reason, source, goal_name, payload) "
                    "VALUES ('2026-08-01', 'test', 'legacy-json', ?, ?)",
                    ("goal_name", "payload"),
                ),
            }
            self.assertEqual(
                set(inserts), set(ENCRYPTED_FIELDS),
                "ENCRYPTED_FIELDS değişmiş — bu test yeni tabloyu da "
                "kapsamalı, aksi halde migration'ın onu taşıdığı kanıtsız "
                "kalır.",
            )
            for table, (sql, fields) in inserts.items():
                self.assertEqual(
                    tuple(fields), tuple(ENCRYPTED_FIELDS[table]),
                    f"{table}: test alanları ENCRYPTED_FIELDS ile uyuşmuyor",
                )
                for index in range(2):
                    values = [
                        _TRICKY_VALUES[
                            (index * len(fields) + position)
                            % len(_TRICKY_VALUES)
                        ]
                        for position in range(len(fields))
                    ]
                    cursor = conn.execute(
                        sql, tuple(_legacy_encrypt(v) for v in values))
                    for field, plaintext in zip(fields, values):
                        expected[(table, cursor.lastrowid, field)] = plaintext
            conn.commit()
        return expected

    def _stored(self, table, row_id, field):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return conn.execute(
                f"SELECT {field} FROM {table} WHERE id = ?", (row_id,)
            ).fetchone()[0]

    def test_inventory_counts_every_legacy_field(self):
        plan = inspect_legacy_encryption(db_path=self.db_path)
        self.assertEqual(plan.legacy_fields, len(self.expected))

        self.assertEqual(plan.affected_records, 2 * len(ENCRYPTED_FIELDS))

    def test_every_table_migrates_and_plaintext_survives(self):
        result = migrate_legacy_encryption(
            self.PASSPHRASE,
            self.backup_path,
            db_path=self.db_path,
            key_path=self.key_path,
        )
        self.assertEqual(result["migrated_fields"], len(self.expected))

        untouched, corrupted = [], []
        for (table, row_id, field), plaintext in self.expected.items():
            stored = str(self._stored(table, row_id, field))
            if not stored.startswith(_AEAD_PREFIX):
                untouched.append(f"{table}.{field}#{row_id}")
            elif decrypt(stored) != plaintext:
                corrupted.append(f"{table}.{field}#{row_id}")

        self.assertEqual(untouched, [], "legacy formatta kalan alanlar")
        self.assertEqual(corrupted, [], "düz metni bozulan alanlar")


        migrated_tables = {table for table, _, _ in self.expected}
        self.assertEqual(migrated_tables, set(ENCRYPTED_FIELDS))

    def test_second_run_is_a_no_op(self):
        migrate_legacy_encryption(
            self.PASSPHRASE, self.backup_path,
            db_path=self.db_path, key_path=self.key_path,
        )
        snapshot = {
            key: self._stored(*key) for key in self.expected
        }
        again = migrate_legacy_encryption(
            self.PASSPHRASE, self.backup_path,
            db_path=self.db_path, key_path=self.key_path,
        )
        self.assertTrue(again["already_current"])
        self.assertEqual(again["migrated_fields"], 0)
        self.assertEqual(
            {key: self._stored(*key) for key in self.expected}, snapshot,
            "idempotent çalıştırma ciphertext'i yeniden yazmamalı",
        )


if __name__ == "__main__":
    unittest.main()
