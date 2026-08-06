"""Yarım restore kurtarması GERÇEK açılış yolunda çalışmalı.

Bir kurtarma fonksiyonunun yalnızca unit testte çalışması, gerçek crash
recovery'yi kapatmaz. Bu testler iki şeyi ayrı ayrı kanıtlar:

1. `main.py::build` kurtarmayı anahtar/DB/config'e dokunan her şeyden ÖNCE
   çağırıyor (çağrı sırası testi).
2. Kurtarma başarısız olduğunda açılış FAIL-CLOSED duruyor — DB
   initialization ve migration hiç çalışmıyor.
"""

import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from services.startup_recovery import (
    RecoveryOutcome,
    StartupRecoveryError,
    run_startup_recovery,
)


class StartupRecoveryContractTest(unittest.TestCase):
    """`run_startup_recovery` sözleşmesi."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.db_path = self.root / "finance.db"
        self.db_path.write_bytes(b"eski-db")
        self.journal = self.root / ".archlence-restore"

    def tearDown(self):
        self.tempdir.cleanup()

    def test_no_journal_is_not_required(self):
        outcome, _ = run_startup_recovery(db_path=str(self.db_path))
        self.assertIs(outcome, RecoveryOutcome.NOT_REQUIRED)

    def test_completed_recovery_restores_the_old_generation(self):
        self.journal.mkdir(mode=0o700)
        (self.journal / "old-finance.db").write_bytes(b"kurtarilan-db")
        (self.journal / "journal.json").write_text(
            json.dumps({
                "state": "DB_REPLACED",
                "db_path": str(self.db_path),
                "config_path": None,
                "had_config": False,
            }),
            encoding="utf-8",
        )
        outcome, result = run_startup_recovery(db_path=str(self.db_path))
        self.assertIs(outcome, RecoveryOutcome.COMPLETED)
        self.assertTrue(result["recovered"])
        self.assertEqual(self.db_path.read_bytes(), b"kurtarilan-db")
        self.assertFalse(self.journal.exists())

    def test_malformed_journal_fails_closed(self):
        self.journal.mkdir(mode=0o700)
        (self.journal / "journal.json").write_text("{bozuk", encoding="utf-8")
        with self.assertRaises(StartupRecoveryError) as ctx:
            run_startup_recovery(db_path=str(self.db_path))
        self.assertIs(
            ctx.exception.outcome,
            RecoveryOutcome.MANUAL_INTERVENTION_REQUIRED,
        )
        # Bozuk journal SESSİZCE SİLİNMEMELİ — elle inceleme gerekiyor.
        self.assertTrue(self.journal.exists())

    def test_unknown_state_fails_closed(self):
        self.journal.mkdir(mode=0o700)
        (self.journal / "journal.json").write_text(
            json.dumps({"state": "UYDURMA"}), encoding="utf-8"
        )
        with self.assertRaises(StartupRecoveryError):
            run_startup_recovery(db_path=str(self.db_path))

    def test_error_message_leaks_no_paths_or_state(self):
        self.journal.mkdir(mode=0o700)
        (self.journal / "journal.json").write_text("{bozuk", encoding="utf-8")
        with self.assertRaises(StartupRecoveryError) as ctx:
            run_startup_recovery(db_path=str(self.db_path))
        message = str(ctx.exception)
        self.assertNotIn(str(self.db_path), message)
        self.assertNotIn("journal", message.lower())
        self.assertIn("korundu", message)

    def test_recovery_is_idempotent(self):
        self.journal.mkdir(mode=0o700)
        (self.journal / "old-finance.db").write_bytes(b"kurtarilan-db")
        (self.journal / "journal.json").write_text(
            json.dumps({
                "state": "DB_REPLACED",
                "db_path": str(self.db_path),
                "config_path": None,
                "had_config": False,
            }),
            encoding="utf-8",
        )
        run_startup_recovery(db_path=str(self.db_path))
        first = self.db_path.read_bytes()
        outcome, _ = run_startup_recovery(db_path=str(self.db_path))
        self.assertIs(outcome, RecoveryOutcome.NOT_REQUIRED)
        self.assertEqual(self.db_path.read_bytes(), first)


class StartupCallOrderTest(unittest.TestCase):
    """`main.py::build` kurtarmayı DOĞRU SIRADA çağırıyor mu.

    Asıl kanıt bu: fonksiyonun var olması yetmez, açılış yolunda ve
    anahtar/DB/config'ten ÖNCE çağrılması gerekir.
    """

    def _run_build_recording_order(self, recovery_side_effect=None):
        """`build()`in ilgili kısmını çağırır ve çağrı sırasını kaydeder."""
        import main as archlence_main

        order = []

        def _record(name, result=None, side_effect=None):
            def _fn(*args, **kwargs):
                order.append(name)
                if side_effect:
                    raise side_effect
                return result
            return _fn

        app = archlence_main.ArchlenceApp.__new__(
            archlence_main.ArchlenceApp
        )

        patches = [
            mock.patch.object(
                archlence_main, "setup_appimage_desktop_integration",
                _record("appimage"),
            ),
            mock.patch(
                "services.startup_recovery.run_startup_recovery",
                _record("recovery", side_effect=recovery_side_effect),
            ),
            mock.patch.object(
                archlence_main.ArchlenceApp, "_warm_crypto_key_in_background",
                _record("key_load"),
            ),
            mock.patch.object(
                archlence_main, "migrate_legacy_database_location",
                _record("legacy_migration"),
            ),
            mock.patch.object(
                archlence_main, "initialize_database",
                _record("database_init"),
            ),
            # build()'in geri kalanını erken durdur: sıradaki ilk adım
            # config okuması, orada kontrollü çıkıyoruz.
            mock.patch.object(
                archlence_main, "JsonStore",
                _record("config_store", side_effect=_StopBuild()),
            ),
            mock.patch.object(archlence_main, "Clock", mock.MagicMock()),
            mock.patch(
                "services.background_task_manager.BackgroundTaskManager",
                mock.MagicMock(),
            ),
        ]
        for patch in patches:
            patch.start()
        self.addCleanup(lambda: [p.stop() for p in patches])

        raised = None
        try:
            app.build()
        except (_StopBuild, StartupRecoveryError) as exc:
            raised = exc
        except Exception as exc:                       # noqa: BLE001
            raised = exc
        return order, raised

    def test_recovery_runs_before_key_database_and_config(self):
        order, _ = self._run_build_recording_order()
        self.assertIn("recovery", order, "kurtarma açılış yolunda çağrılmıyor")
        for later in ("key_load", "database_init", "config_store"):
            if later in order:
                self.assertLess(
                    order.index("recovery"), order.index(later),
                    f"kurtarma {later} adımından SONRA çağrılıyor",
                )

    def test_failed_recovery_stops_startup_before_database_init(self):
        order, raised = self._run_build_recording_order(
            recovery_side_effect=StartupRecoveryError(
                "test", outcome=RecoveryOutcome.MANUAL_INTERVENTION_REQUIRED
            )
        )
        self.assertIsInstance(raised, StartupRecoveryError)
        self.assertNotIn(
            "database_init", order,
            "kurtarma başarısızken veritabanı yine de açıldı",
        )
        self.assertNotIn(
            "key_load", order,
            "kurtarma başarısızken anahtar yine de yüklendi",
        )
        self.assertNotIn("legacy_migration", order)


class _StopBuild(Exception):
    """build()'i kontrollü noktada durdurmak için."""


if __name__ == "__main__":
    unittest.main()
