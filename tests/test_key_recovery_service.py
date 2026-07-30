import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from services.key_recovery_service import (
    export_recovery_package,
    import_recovery_package,
    read_recovery_package,
    rotate_encryption_key,
)
from utils.errors import DataMigrationError, IntegrityVerificationError
from utils.key_provider import FileKeyProvider


class KeyRecoveryIntegrationTest(unittest.TestCase):
    PASSWORD = "guclu-kurtarma-parolasi"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.db = root / "finance.db"
        self.key_path = root / "encryption.key"
        self.recovery = root / "recovery.json"
        self.backup = root / "rotation.backup"
        self.provider = FileKeyProvider(str(self.key_path))
        self.key = self.provider.get_or_create_key()
        self.db_patch = mock.patch("database.db.DB_NAME", str(self.db))
        self.crypto_patch = mock.patch(
            "utils.crypto._get_aead_key", return_value=self.key
        )
        self.db_patch.start()
        self.crypto_patch.start()
        from database.init_db import initialize_database
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        initialize_database()
        account = AccountService.create_account(
            "Rotasyon", "checking", initial_balance=1000
        )
        TransactionService.add_transaction(
            account, 12.34, "expense", "Market", "gizli"
        )

    def tearDown(self):
        self.crypto_patch.stop()
        self.db_patch.stop()
        self.temp.cleanup()

    def test_recovery_export_import_and_wrong_password(self):
        export_recovery_package(
            self.recovery, self.PASSWORD, self.provider
        )
        raw = self.recovery.read_bytes()
        self.assertNotIn(self.key, raw)
        self.assertEqual(
            read_recovery_package(self.recovery, self.PASSWORD), self.key
        )
        with self.assertRaises(IntegrityVerificationError):
            read_recovery_package(self.recovery, "yanlis-parola-123")

        wrong = os.urandom(32)
        self.provider.replace_key(wrong, expected_current=self.key)
        result = import_recovery_package(
            self.recovery, self.PASSWORD, self.provider, self.db
        )
        self.assertTrue(result["imported"])
        self.assertEqual(self.provider.load_key(), self.key)

    def test_tampered_recovery_package_is_rejected(self):
        export_recovery_package(
            self.recovery, self.PASSWORD, self.provider
        )
        payload = json.loads(self.recovery.read_text(encoding="utf-8"))
        payload["recovery"]["ciphertext"] = "AAAA"
        self.recovery.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(IntegrityVerificationError):
            read_recovery_package(self.recovery, self.PASSWORD)

    def test_rotation_reencrypts_and_blocks_duplicate_old_request(self):
        old_fingerprint = hashlib.sha256(self.key).hexdigest()
        result = rotate_encryption_key(
            db_path=self.db,
            provider=self.provider,
            backup_path=self.backup,
            backup_passphrase=self.PASSWORD,
            rotation_id="rotation-1",
            expected_fingerprint=old_fingerprint,
        )
        self.assertGreaterEqual(result["rotated_fields"], 2)
        self.assertTrue(self.backup.exists())
        self.assertNotEqual(self.provider.load_key(), self.key)
        with self.assertRaises(DataMigrationError):
            rotate_encryption_key(
                db_path=self.db,
                provider=self.provider,
                backup_path=self.backup,
                backup_passphrase=self.PASSWORD,
                rotation_id="rotation-1",
                expected_fingerprint=old_fingerprint,
            )

    def test_rotation_failure_after_key_swap_rolls_back_db_and_key(self):
        old_fingerprint = hashlib.sha256(self.key).hexdigest()
        with closing(sqlite3.connect(self.db)) as conn:
            before = conn.execute(
                "SELECT amount, description FROM transactions"
            ).fetchall()

        def fail(stage, count):
            if stage == "after_key_replace":
                raise OSError("injected replace failure")

        with self.assertRaises(DataMigrationError):
            rotate_encryption_key(
                db_path=self.db,
                provider=self.provider,
                backup_path=self.backup,
                backup_passphrase=self.PASSWORD,
                rotation_id="rotation-fail",
                expected_fingerprint=old_fingerprint,
                _failure_hook=fail,
            )
        self.assertEqual(self.provider.load_key(), self.key)
        with closing(sqlite3.connect(self.db)) as conn:
            after = conn.execute(
                "SELECT amount, description FROM transactions"
            ).fetchall()
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
