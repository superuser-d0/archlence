import base64
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from services.crypto_migration_service import (
    inspect_legacy_encryption,
    migrate_legacy_encryption,
)
from utils.crypto import DEFAULT_PASSWORD, STATIC_SALT, decrypt
from utils.errors import DataMigrationError
from Crypto.Protocol.KDF import PBKDF2


def _legacy_encrypt(value):
    iv = bytes(range(16))
    key = PBKDF2(DEFAULT_PASSWORD, STATIC_SALT, dkLen=32, count=1_000_000)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    payload = iv + cipher.encrypt(pad(str(value).encode("utf-8"), 16))
    return base64.b64encode(payload).decode("ascii")


class CryptoMigrationIntegrationTest(unittest.TestCase):
    PASSPHRASE = "migration-backup-parolasi"

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
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO recurring_payments "
                "(name, amount, category, frequency, next_due_date, "
                "is_active) VALUES (?, ?, ?, ?, ?, 1)",
                (
                    _legacy_encrypt("Legacy Maaş"),
                    _legacy_encrypt("1500.25"),
                    "Maaş",
                    "monthly",
                    "2026-08-15",
                ),
            )
            conn.commit()

    def tearDown(self):
        self.crypto_key_patch.stop()
        self.db_patch.stop()
        self.tempdir.cleanup()

    def _encrypted_values(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return conn.execute(
                "SELECT name, amount FROM recurring_payments"
            ).fetchone()

    def test_migration_is_backup_first_verified_and_idempotent(self):
        plan = inspect_legacy_encryption(db_path=self.db_path)
        self.assertEqual(plan.legacy_fields, 2)
        self.assertEqual(plan.affected_records, 1)

        result = migrate_legacy_encryption(
            self.PASSPHRASE,
            self.backup_path,
            db_path=self.db_path,
            key_path=self.key_path,
        )
        self.assertEqual(result["migrated_fields"], 2)
        self.assertTrue(self.backup_path.is_file())
        name, amount = self._encrypted_values()
        self.assertTrue(name.startswith("AEADv1:"))
        self.assertTrue(amount.startswith("AEADv1:"))
        self.assertEqual(decrypt(name), "Legacy Maaş")
        self.assertEqual(decrypt(amount), "1500.25")

        again = migrate_legacy_encryption(
            self.PASSPHRASE,
            self.backup_path,
            db_path=self.db_path,
            key_path=self.key_path,
        )
        self.assertTrue(again["already_current"])
        self.assertEqual(again["migrated_fields"], 0)
        self.assertEqual(self._encrypted_values(), (name, amount))

    def test_failure_rolls_back_every_field(self):
        before = self._encrypted_values()

        def fail_after_first(migrated):
            if migrated == 1:
                raise OSError("injected migration write failure")

        with self.assertRaises(DataMigrationError):
            migrate_legacy_encryption(
                self.PASSPHRASE,
                self.backup_path,
                db_path=self.db_path,
                key_path=self.key_path,
                _failure_hook=fail_after_first,
            )
        self.assertEqual(self._encrypted_values(), before)
        self.assertTrue(self.backup_path.is_file())
        self.assertEqual(
            inspect_legacy_encryption(db_path=self.db_path).legacy_fields, 2
        )

    def test_corrupt_legacy_value_aborts_without_mutation(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "UPDATE recurring_payments SET amount = ?",
                ("not-valid-ciphertext",),
            )
            conn.commit()
        before = self._encrypted_values()
        with self.assertRaises(DataMigrationError):
            migrate_legacy_encryption(
                self.PASSPHRASE,
                self.backup_path,
                db_path=self.db_path,
                key_path=self.key_path,
            )
        self.assertEqual(self._encrypted_values(), before)


if __name__ == "__main__":
    unittest.main()
