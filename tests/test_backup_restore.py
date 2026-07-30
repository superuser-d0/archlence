import os
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest import mock

from services.backup_service import (
    create_backup,
    restore_backup,
    verify_backup,
)
from utils.errors import DataMigrationError, IntegrityVerificationError


class BackupRestoreIntegrationTest(unittest.TestCase):
    PASSPHRASE = "test-kurtarma-parolasi-2026"

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.db_path = root / "finance.db"
        self.key_path = root / "encryption.key"
        self.package = root / "backup.archlence-backup"
        self.safety = root / "safety.archlence-backup"
        self.key = os.urandom(32)
        self.key_path.write_bytes(self.key)
        os.chmod(self.key_path, 0o600)

        self.db_patch = mock.patch("database.db.DB_NAME", str(self.db_path))
        self.key_patch = mock.patch(
            "utils.crypto._get_aead_key", return_value=self.key
        )
        self.db_patch.start()
        self.key_patch.start()

        from database.init_db import initialize_database
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        initialize_database()
        self.account_id = AccountService.create_account(
            "Backup Hesabı", "checking", initial_balance=1000
        )
        TransactionService.add_transaction(
            self.account_id, 125.50, "expense", "Market", "Gizli açıklama"
        )

    def tearDown(self):
        self.key_patch.stop()
        self.db_patch.stop()
        self.tempdir.cleanup()

    def _create(self):
        return create_backup(
            self.package,
            self.PASSPHRASE,
            db_path=self.db_path,
            key_path=self.key_path,
        )

    def test_backup_contains_no_raw_key_and_is_restore_verifiable(self):
        result = self._create()
        self.assertGreaterEqual(result["aead_records_verified"], 2)

        with zipfile.ZipFile(self.package) as archive:
            names = set(archive.namelist())
            self.assertEqual(
                names,
                {"finance.db", "metadata.json", "key.recovery.json"},
            )
            recovery = archive.read("key.recovery.json")
            self.assertNotIn(self.key, recovery)
            self.assertNotIn(b"Gizli a", recovery)

        verified = verify_backup(self.package, self.PASSPHRASE)
        self.assertEqual(verified["key"], self.key)

    def test_wrong_passphrase_is_rejected(self):
        self._create()
        with self.assertRaises(IntegrityVerificationError):
            verify_backup(self.package, "yanlis-parola-123")

    def test_tampered_database_is_rejected(self):
        self._create()
        unpacked = Path(self.tempdir.name) / "tampered"
        unpacked.mkdir()
        with zipfile.ZipFile(self.package) as archive:
            archive.extractall(unpacked)
        with open(unpacked / "finance.db", "ab") as stream:
            stream.write(b"tamper")
        tampered = Path(self.tempdir.name) / "tampered.zip"
        with zipfile.ZipFile(tampered, "w") as archive:
            for name in ("finance.db", "metadata.json", "key.recovery.json"):
                archive.write(unpacked / name, name)
        with self.assertRaises(IntegrityVerificationError):
            verify_backup(tampered, self.PASSPHRASE)

    def test_restore_takes_safety_backup_and_restores_matching_key(self):
        self._create()
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "UPDATE accounts SET balance = 9999 WHERE id = ?",
                (self.account_id,),
            )
            conn.commit()

        result = restore_backup(
            self.package,
            self.PASSPHRASE,
            db_path=self.db_path,
            key_path=self.key_path,
            safety_backup_path=self.safety,
        )

        self.assertTrue(result["restored"])
        self.assertTrue(self.safety.exists())
        self.assertEqual(self.key_path.read_bytes(), self.key)
        with closing(sqlite3.connect(self.db_path)) as conn:
            balance = conn.execute(
                "SELECT balance FROM accounts WHERE id = ?",
                (self.account_id,),
            ).fetchone()[0]
        self.assertEqual(balance, 874.5)

    def test_restore_failure_rolls_back_current_database_and_key(self):
        self._create()
        current_key = self.key_path.read_bytes()
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "UPDATE accounts SET balance = 4321 WHERE id = ?",
                (self.account_id,),
            )
            conn.commit()

        def fail(stage):
            if stage == "after_database_replaced":
                raise OSError("injected disk failure")

        with self.assertRaises(DataMigrationError):
            restore_backup(
                self.package,
                self.PASSPHRASE,
                db_path=self.db_path,
                key_path=self.key_path,
                safety_backup_path=self.safety,
                _failure_hook=fail,
            )

        self.assertEqual(self.key_path.read_bytes(), current_key)
        with closing(sqlite3.connect(self.db_path)) as conn:
            balance = conn.execute(
                "SELECT balance FROM accounts WHERE id = ?",
                (self.account_id,),
            ).fetchone()[0]
        self.assertEqual(balance, 4321)


if __name__ == "__main__":
    unittest.main()
