"""COMMITTED sonrası çökme BAŞARILI restore'u geri almamalı.

Denetim bulgusu (P1-1 kalan alt bileşen): journal başarıda doğrudan
siliniyordu, yani post-verification ile silme arasında çöken bir süreç
journal'ı `CONFIG_REPLACED` durumunda bırakıyor ve sonraki açılış BAŞARIYLA
TAMAMLANMIŞ bir restore'u geri alıyordu.

Semantik artık açık:

    state < COMMITTED   -> eski generation canonical, startup geri alır
    state >= COMMITTED  -> yeni generation canonical, startup yalnız temizler
    bozuk/bilinmeyen    -> fail-closed
"""

import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from services.backup_service import (
    create_backup,
    recover_interrupted_restore,
    restore_backup,
)
from utils.errors import DataMigrationError


class _Crash(BaseException):
    """`except Exception` tarafından yakalanmaz — gerçek kill -9 karşılığı."""


class RestoreCommittedRecoveryTest(unittest.TestCase):
    PASSPHRASE = "test-kurtarma-parolasi-2026"

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.db_path = root / "finance.db"
        self.key_path = root / "encryption.key"
        self.config_path = root / "config.json"
        self.package = root / "backup.archlence-backup"
        self.safety = root / "safety.archlence-backup"
        self.journal = root / ".archlence-restore"
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

        initialize_database()
        AccountService.create_account(
            "Yedek Hesabı", "checking", initial_balance=1000
        )

        # Backup state: balance 4321, config "from-backup".
        self.config_path.write_text('{"profile":"from-backup"}',
                                    encoding="utf-8")
        self._set_balance(4321.0)
        create_backup(
            self.package, self.PASSPHRASE,
            db_path=self.db_path, key_path=self.key_path,
            config_path=str(self.config_path),
        )

        # Current profile differs: balance 9999, config "current".
        self._set_balance(9999.0)
        self.config_path.write_text('{"profile":"current"}', encoding="utf-8")

    def tearDown(self):
        self.key_patch.stop()
        self.db_patch.stop()
        self.tempdir.cleanup()

    def _set_balance(self, value):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("UPDATE accounts SET balance=?", (value,))
            conn.commit()

    def _balance(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return conn.execute("SELECT balance FROM accounts").fetchone()[0]

    def _restore_crashing_at(self, point):
        def _hook(where):
            if where == point:
                raise _Crash(f"simulated kill at {where}")

        with self.assertRaises(_Crash):
            restore_backup(
                self.package, self.PASSPHRASE,
                db_path=self.db_path, key_path=self.key_path,
                config_path=str(self.config_path),
                safety_backup_path=self.safety,
                _failure_hook=_hook,
            )

    def _journal_state(self):
        payload = json.loads(
            (self.journal / "journal.json").read_text(encoding="utf-8")
        )
        return payload["state"]


    def test_crash_before_committed_marker_rolls_back(self):
        self._restore_crashing_at("before_committed_marker")
        self.assertEqual(self._journal_state(), "VERIFIED")

        result = recover_interrupted_restore(
            db_path=self.db_path, config_path=str(self.config_path)
        )
        self.assertEqual(result["action"], "rolled-back")
        self.assertEqual(self._balance(), 9999.0, "eski generation dönmedi")
        self.assertEqual(
            self.config_path.read_text(encoding="utf-8"),
            '{"profile":"current"}',
        )
        self.assertFalse(self.journal.exists())


    def test_crash_after_committed_marker_keeps_the_new_generation(self):
        self._restore_crashing_at("after_committed_marker")
        self.assertEqual(self._journal_state(), "COMMITTED")

        result = recover_interrupted_restore(
            db_path=self.db_path, config_path=str(self.config_path)
        )
        self.assertEqual(
            result["action"], "cleanup-only",
            "başarılı restore geri alındı",
        )
        self.assertEqual(
            self._balance(), 4321.0,
            "COMMITTED sonrası yeni generation korunmadı",
        )
        self.assertEqual(
            self.config_path.read_text(encoding="utf-8"),
            '{"profile":"from-backup"}',
        )
        self.assertFalse(self.journal.exists(), "temizlik tamamlanmadı")

    def test_committed_cleanup_is_idempotent(self):
        self._restore_crashing_at("after_committed_marker")
        recover_interrupted_restore(
            db_path=self.db_path, config_path=str(self.config_path)
        )
        first_hash = hashlib.sha256(self.db_path.read_bytes()).hexdigest()

        second = recover_interrupted_restore(
            db_path=self.db_path, config_path=str(self.config_path)
        )
        self.assertFalse(second["recovered"])
        self.assertEqual(
            hashlib.sha256(self.db_path.read_bytes()).hexdigest(),
            first_hash,
            "ikinci kurtarma veriyi değiştirdi",
        )
        self.assertEqual(self._balance(), 4321.0)

    def test_cleanup_state_is_also_treated_as_committed(self):
        """`CLEANUP_COMPLETE` de yeni generation'ı canonical saymalı."""
        self._restore_crashing_at("after_committed_marker")
        payload = json.loads(
            (self.journal / "journal.json").read_text(encoding="utf-8")
        )
        payload["state"] = "CLEANUP_COMPLETE"
        (self.journal / "journal.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        result = recover_interrupted_restore(
            db_path=self.db_path, config_path=str(self.config_path)
        )
        self.assertEqual(result["action"], "cleanup-only")
        self.assertEqual(self._balance(), 4321.0)

    # ── COMMITTED without a new database: fail closed ───────────────────

    def test_committed_without_the_new_database_fails_closed(self):
        self._restore_crashing_at("after_committed_marker")
        self.db_path.unlink()

        with self.assertRaises(DataMigrationError):
            recover_interrupted_restore(
                db_path=self.db_path, config_path=str(self.config_path)
            )

        self.assertTrue(
            self.journal.exists(),
            "fail-closed olması gereken durumda journal silindi",
        )
        self.assertFalse(self.db_path.exists())


    def test_a_clean_successful_restore_leaves_no_journal(self):
        restore_backup(
            self.package, self.PASSPHRASE,
            db_path=self.db_path, key_path=self.key_path,
            config_path=str(self.config_path),
            safety_backup_path=self.safety,
        )
        self.assertEqual(self._balance(), 4321.0)
        self.assertFalse(self.journal.exists())
        result = recover_interrupted_restore(db_path=self.db_path)
        self.assertFalse(result["recovered"])


if __name__ == "__main__":
    unittest.main()
