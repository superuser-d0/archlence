"""Restore, DB + key + config'i TEK BİR generation olarak ele almalı.

Denetim bulgusu P1-1: eski kod başarısız restore'da DB ve anahtarı geri
alıyordu ama config'i almıyordu — profil karma durumda kalıyordu (DB eski,
config yedekten). Ayrıca rollback generation `TemporaryDirectory` içindeydi;
süreç replacement ile doğrulama arasında ÇÖKERSE o dizin silinir ve geri
dönülecek hiçbir şey kalmazdı.

Bu testler her replacement adımından sonra hata enjekte edip üç dosyanın da
restore ÖNCESİ hâline döndüğünü doğrular, ve yarım kalmış bir restore'un
sonraki açılışta toparlandığını gösterir.
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


class RestoreGenerationAtomicityTest(unittest.TestCase):
    PASSPHRASE = "test-kurtarma-parolasi-2026"

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.db_path = root / "finance.db"
        self.key_path = root / "encryption.key"
        self.config_path = root / "config.json"
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

        initialize_database()
        AccountService.create_account(
            "Yedek Hesabı", "checking", initial_balance=1000
        )

        # Yedeğin içeriği: "from-backup" config + 4321 bakiye.
        self.config_path.write_text('{"profile":"from-backup"}',
                                    encoding="utf-8")
        self._set_balance(4321.0)
        create_backup(
            self.package, self.PASSPHRASE,
            db_path=self.db_path, key_path=self.key_path,
            config_path=str(self.config_path),
        )

        # Mevcut profil yedekten FARKLI olsun ki rollback ölçülebilsin.
        self._set_balance(9999.0)
        self.config_path.write_text('{"profile":"current"}', encoding="utf-8")
        self.before = self._snapshot()

    def tearDown(self):
        self.key_patch.stop()
        self.db_patch.stop()
        self.tempdir.cleanup()

    def _set_balance(self, value):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("UPDATE accounts SET balance=?", (value,))
            conn.commit()

    def _snapshot(self):
        """DB baytları, anahtar baytları, config metni ve bakiye."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            balance = conn.execute(
                "SELECT balance FROM accounts"
            ).fetchone()[0]
        return {
            "db_sha": hashlib.sha256(self.db_path.read_bytes()).hexdigest(),
            "key": self.key_path.read_bytes(),
            "config": self.config_path.read_text(encoding="utf-8"),
            "balance": balance,
        }

    def _restore(self, fault_at=None):
        def _hook(point):
            if fault_at and point == fault_at:
                raise OSError(f"injected at {point}")

        return restore_backup(
            self.package, self.PASSPHRASE,
            db_path=self.db_path, key_path=self.key_path,
            config_path=str(self.config_path),
            safety_backup_path=self.safety,
            _failure_hook=_hook if fault_at else None,
        )

    # ── Başarısız restore: üç dosya da birlikte geri dönmeli ──────────────

    def test_every_replacement_fault_rolls_back_the_whole_generation(self):
        for fault in (
            "after_old_files_staged",
            "after_database_replaced",
            "after_key_replaced",
            "after_config_replaced",
            "after_post_verification",
        ):
            with self.subTest(fault=fault):
                # Her fault için TAZE profil: önceki fixture kapatılıp
                # yenisi kuruluyor, aksi halde tempdir orphan kalırdı.
                self.tearDown()
                self.setUp()
                try:
                    with self.assertRaises(DataMigrationError):
                        self._restore(fault_at=fault)
                    after = self._snapshot()
                    self.assertEqual(
                        after["db_sha"], self.before["db_sha"],
                        f"{fault}: DB geri gelmedi",
                    )
                    self.assertEqual(
                        after["key"], self.before["key"],
                        f"{fault}: anahtar geri gelmedi",
                    )
                    self.assertEqual(
                        after["config"], self.before["config"],
                        f"{fault}: config geri gelmedi (karma profil)",
                    )
                    self.assertEqual(after["balance"], 9999.0)
                    self.assertFalse(
                        (self.db_path.parent / ".archlence-restore").exists(),
                        f"{fault}: journal temizlenmedi",
                    )
                finally:
                    pass

    def test_config_is_removed_again_when_it_did_not_exist_before(self):
        """Restore öncesi config YOKSA, başarısızlıkta yaratılmamalı."""
        self.config_path.unlink()
        with self.assertRaises(DataMigrationError):
            self._restore(fault_at="after_config_replaced")
        self.assertFalse(
            self.config_path.exists(),
            "restore öncesi olmayan config başarısızlıktan sonra kaldı",
        )

    # ── Başarılı restore ─────────────────────────────────────────────────

    def test_successful_restore_applies_one_complete_generation(self):
        result = self._restore()
        self.assertTrue(result["restored"])
        after = self._snapshot()
        self.assertEqual(after["balance"], 4321.0)
        self.assertEqual(after["config"], '{"profile":"from-backup"}')
        self.assertFalse(
            (self.db_path.parent / ".archlence-restore").exists(),
            "başarılı restore sonrası journal kaldı",
        )

    # ── Yarım kalmış restore: başlangıç kurtarması ───────────────────────

    def test_interrupted_restore_is_recovered_on_startup(self):
        """Süreç replacement'tan sonra çökerse sonraki açılış toparlamalı.

        Çökme, rollback yolunu HİÇ çalıştırmadan çıkarak taklit ediliyor:
        `BaseException` `except Exception` tarafından yakalanmaz, yani journal
        ve eski generation diskte kalır — gerçek bir kill -9 sonrası duruma
        denk.
        """
        class _Crash(BaseException):
            pass

        def _hook(point):
            if point == "after_database_replaced":
                raise _Crash("simulated process kill")

        with self.assertRaises(_Crash):
            restore_backup(
                self.package, self.PASSPHRASE,
                db_path=self.db_path, key_path=self.key_path,
                config_path=str(self.config_path),
                safety_backup_path=self.safety,
                _failure_hook=_hook,
            )

        journal = self.db_path.parent / ".archlence-restore"
        self.assertTrue(journal.exists(), "journal yazılmamış; kurtarma imkânsız")

        result = recover_interrupted_restore(
            db_path=self.db_path, config_path=str(self.config_path)
        )
        self.assertTrue(result["recovered"])
        after = self._snapshot()
        self.assertEqual(after["db_sha"], self.before["db_sha"])
        self.assertEqual(after["config"], self.before["config"])
        self.assertEqual(after["balance"], 9999.0)
        self.assertFalse(journal.exists(), "kurtarma sonrası journal kaldı")

    def test_recovery_is_a_no_op_without_a_journal(self):
        result = recover_interrupted_restore(db_path=self.db_path)
        self.assertFalse(result["recovered"])
        self.assertEqual(result["reason"], "no-journal")

    def test_corrupt_journal_fails_closed(self):
        """Bozuk journal sessizce yok sayılmamalı."""
        journal = self.db_path.parent / ".archlence-restore"
        journal.mkdir(mode=0o700)
        (journal / "journal.json").write_text("{bozuk", encoding="utf-8")
        with self.assertRaises(DataMigrationError):
            recover_interrupted_restore(db_path=self.db_path)

    def test_unknown_journal_state_fails_closed(self):
        journal = self.db_path.parent / ".archlence-restore"
        journal.mkdir(mode=0o700)
        (journal / "journal.json").write_text(
            json.dumps({"state": "UYDURMA"}), encoding="utf-8"
        )
        with self.assertRaises(DataMigrationError):
            recover_interrupted_restore(db_path=self.db_path)


if __name__ == "__main__":
    unittest.main()
