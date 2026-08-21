"""Bütünlük kapısı, veritabanına DOKUNMADAN önce durmalı.

ÖLÇÜLEN KUSUR: kapı şema kuşağının SONUNDAydı. Yani `CREATE TABLE`,
`ALTER TABLE`, backfill adımları ve `PRAGMA user_version = 2` yazımı çoktan
commit edilmiş oluyordu. Öksüz satır taşıyan bir profilde ölçüldü —
`initialize_database()` `FinancialDataIntegrityError` fırlatmasına RAĞMEN:

    user_version      : 1  ->  2
    "Varlık Alımı"    : silinmiş kategori GERİ YAZILDI (0 -> 1)
    finance.db sha256 : fe30c68a...  ->  1fec865d...

Yani hatanın kendi metnindeki "Hiçbir kayıt değiştirilmedi" iddiası YANLIŞTI:
uygulama, bozuk olduğunu söylediği veritabanını önce değiştiriyordu.

İKİNCİ KUSUR: `main.py::build` yalnız `SchemaTooNewError` yakalıyordu.
`FinancialDataIntegrityError` ham hâliyle dışarı taşıyor, kullanıcı güvenli
bir ekran yerine çökme görüyordu — üstelik exception metni tablo adı ve rowid
taşıyor.
"""
import hashlib
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from database.init_db import DATA_INTEGRITY_MESSAGE
from utils.errors import FinancialDataIntegrityError

_TX_INSERT = (
    "INSERT INTO transactions "
    "(account_id, amount, type, category, description, transaction_date) "
    "VALUES (?, ?, ?, ?, ?, ?)"
)
_ORPHAN_ACCOUNT = 424242


class _ProfileFixture(unittest.TestCase):
    """Öksüz satır taşıyan, eski kuşaktan bir profil kurar."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "finance.db"
        self.key = os.urandom(32)
        self.db_patch = mock.patch("database.db.DB_NAME", str(self.db_path))
        self.key_patch = mock.patch(
            "utils.crypto._get_aead_key", return_value=self.key
        )
        self.db_patch.start()
        self.key_patch.start()
        self.addCleanup(self.tempdir.cleanup)
        self.addCleanup(self.db_patch.stop)
        self.addCleanup(self.key_patch.stop)

        from database.init_db import initialize_database

        initialize_database()

    def _make_legacy_orphaned(self):
        """Zorlama KAPALI ham bağlantıyla eski sürümün bıraktığı hâli kurar."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                _TX_INSERT,
                (_ORPHAN_ACCOUNT, "x", "expense", "Eski", "öksüz",
                 "2026-01-01 00:00:00"),
            )


            conn.execute("DELETE FROM categories WHERE name = 'Varlık Alımı'")
            conn.execute("PRAGMA user_version = 1")
            conn.commit()

    def _snapshot(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            user_version = conn.execute("PRAGMA user_version").fetchone()[0]
            category = conn.execute(
                "SELECT COUNT(*) FROM categories WHERE name = 'Varlık Alımı'"
            ).fetchone()[0]
            orphans = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE account_id = ?",
                (_ORPHAN_ACCOUNT,),
            ).fetchone()[0]
        return {
            "user_version": user_version,
            "category": category,
            "orphans": orphans,
            "sha256": hashlib.sha256(self.db_path.read_bytes()).hexdigest(),
        }


class PreflightLeavesTheDatabaseUntouchedTest(_ProfileFixture):
    def test_orphaned_profile_is_byte_for_byte_unchanged(self):
        from database.init_db import initialize_database

        self._make_legacy_orphaned()
        before = self._snapshot()
        self.assertEqual(before["user_version"], 1)
        self.assertEqual(before["category"], 0)
        self.assertEqual(before["orphans"], 1)

        with self.assertRaises(FinancialDataIntegrityError):
            initialize_database()

        after = self._snapshot()
        self.assertEqual(
            after["sha256"], before["sha256"],
            "bozuk profil, hata verilmesine rağmen DEĞİŞTİRİLDİ",
        )
        self.assertEqual(after["user_version"], 1, "user_version yazıldı")
        self.assertEqual(after["category"], 0, "silinmiş kategori geri yazıldı")
        self.assertEqual(after["orphans"], 1, "öksüz satır kaybedildi")

    def test_the_error_carries_diagnosable_detail(self):
        from database.init_db import initialize_database

        self._make_legacy_orphaned()
        with self.assertRaises(FinancialDataIntegrityError) as caught:
            initialize_database()
        self.assertEqual(caught.exception.table, "transactions")
        self.assertIn("accounts", str(caught.exception.reason))

    def test_the_preflight_runs_exactly_once_on_a_healthy_startup(self):
        """Sağlıklı açılışta ikinci bir tam tarama yapılmamalı."""
        import database.init_db as init_db

        calls = []
        real = init_db._foreign_key_violations

        def spy(conn, *args, **kwargs):
            calls.append(1)
            return real(conn, *args, **kwargs)

        with mock.patch.object(init_db, "_foreign_key_violations", spy):
            init_db.initialize_database()
        self.assertEqual(len(calls), 1, f"{len(calls)} kez tarandı")

    def test_the_violation_scan_is_bounded_not_fetchall(self):
        """İhlal listesi sınırsız belleğe alınmamalı."""
        import database.init_db as init_db

        self._make_legacy_orphaned()
        with closing(sqlite3.connect(self.db_path)) as conn:
            for index in range(50):
                conn.execute(
                    _TX_INSERT,
                    (900000 + index, "x", "expense", "Eski", "öksüz",
                     "2026-01-01 00:00:00"),
                )
            conn.commit()

        from database.db import get_connection

        with closing(get_connection()) as conn:
            sample, more = init_db._foreign_key_violations(conn)
        self.assertLessEqual(len(sample), init_db._FK_VIOLATION_SAMPLE)
        self.assertTrue(more, "kalan ihlal olduğu bildirilmedi")

    def test_a_clean_legacy_database_still_upgrades(self):
        from database.init_db import SCHEMA_VERSION, initialize_database
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        account_id = AccountService.create_account(
            "Temiz", "checking", initial_balance=100
        )
        TransactionService.add_transaction(
            account_id, 10.0, "expense", "Market", "temiz"
        )
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("PRAGMA user_version = 1")
            conn.commit()

        initialize_database()

        with closing(sqlite3.connect(self.db_path)) as conn:
            self.assertEqual(
                conn.execute("PRAGMA user_version").fetchone()[0],
                SCHEMA_VERSION,
            )
            self.assertEqual(
                conn.execute("PRAGMA foreign_key_check").fetchall(), []
            )

    def test_a_fresh_database_still_installs(self):
        """Taze DB'de tablo yoktur; preflight güvenli no-op olmalı."""
        from database.init_db import SCHEMA_VERSION, initialize_database

        fresh = Path(self.tempdir.name) / "fresh.db"
        with mock.patch("database.db.DB_NAME", str(fresh)):
            initialize_database()
        with closing(sqlite3.connect(fresh)) as conn:
            self.assertEqual(
                conn.execute("PRAGMA user_version").fetchone()[0],
                SCHEMA_VERSION,
            )
            self.assertTrue(
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE name = 'transactions'"
                ).fetchone()
            )


class StartupPresentationTest(_ProfileFixture):
    """`ArchlenceApp.build` sınırında güvenli sunum."""

    def _run_build(self):
        """Gerçek `build()` gövdesini, bütünlük kapısına kadar çalıştırır."""
        import main

        app = main.ArchlenceApp.__new__(main.ArchlenceApp)
        app.background_tasks = None
        shown = {}

        def present(_app, message):
            shown["message"] = message
            _app._startup_recovery_failure = message
            return object()

        loaded = []
        with mock.patch(
            "services.startup_recovery.present_data_integrity_failure", present
        ), mock.patch.object(
            main.ArchlenceApp, "_run_savings_migration_at_startup",
            lambda self: loaded.append("savings_migration"),
        ), mock.patch.object(
            main.ArchlenceApp, "load_savings_goals",
            lambda self: loaded.append("load_savings_goals"),
        ), mock.patch.object(
            main.ArchlenceApp, "_warm_crypto_key_in_background",
            lambda self: None,
        ), mock.patch("main.setup_appimage_desktop_integration", lambda: None), \
                mock.patch("main.migrate_legacy_database_location", lambda: False), \
                mock.patch("main.Clock"), \
                mock.patch("services.background_task_manager.BackgroundTaskManager"), \
                mock.patch("services.startup_recovery.run_startup_recovery",
                           lambda *a, **k: None):


            root = main.ArchlenceApp.build(app)
        return app, shown, loaded, root

    def test_build_presents_the_safe_screen_and_stops(self):
        self._make_legacy_orphaned()
        app, shown, loaded, root = self._run_build()

        self.assertIsNotNone(root, "açılış hatasında güvenli root dönmedi")
        self.assertEqual(shown.get("message"), DATA_INTEGRITY_MESSAGE)
        self.assertEqual(app._startup_recovery_failure, DATA_INTEGRITY_MESSAGE)
        self.assertEqual(
            loaded, [],
            "bütünlük hatasından sonra veri yükleme yolları çalıştı",
        )

    def test_the_user_message_leaks_no_metadata(self):
        for forbidden in (
            "transactions", "accounts", "rowid", "sqlite", "finance.db",
            str(_ORPHAN_ACCOUNT), "account_id",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden.lower(),
                                 DATA_INTEGRITY_MESSAGE.lower())

    def test_the_log_does_carry_the_technical_detail(self):
        self._make_legacy_orphaned()
        import main

        with mock.patch("utils.logging_config.get_logger") as get_logger:
            self._run_build()
        critical_calls = [
            call for call in get_logger.return_value.critical.call_args_list
        ]
        self.assertTrue(critical_calls, "log'a hiçbir şey yazılmadı")
        rendered = " ".join(
            str(call.args[0]) % call.args[1:] if len(call.args) > 1
            else str(call.args[0])
            for call in critical_calls
        )
        self.assertIn("transactions", rendered)
        self.assertIn("accounts", rendered)
        del main


if __name__ == "__main__":
    unittest.main()
