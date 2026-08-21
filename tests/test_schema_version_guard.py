"""Şema kuşağı işareti ve downgrade koruması (denetim bulgusu A-5).

BULGU: `PRAGMA user_version` sıfırdı, yani veritabanı hangi kuşağa ait
olduğunu HİÇ söylemiyordu. Eski bir yapı, yeni bir yapının yazdığı profili
açıp tanımadığı sütunları görmezden gelerek üzerine yazabilirdi — kişisel
finans verisinde sessiz kayıp.

Bu testler iki şeyi ayrı ayrı sabitler:
  1. İşaret KONUYOR (hem yeni kurulumda hem göç etmiş eski profilde),
  2. Daha yeni bir işaret görüldüğünde açılış DURUYOR ve veriye DOKUNMUYOR.
"""

import os
import sqlite3
import tempfile
import unittest
from unittest import mock

from database.init_db import SCHEMA_TOO_NEW_MESSAGE, SCHEMA_VERSION
from utils.errors import DataMigrationError, SchemaTooNewError


class _TempProfile(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patch = mock.patch("database.db.DB_NAME", self.db_path)
        self._patch.start()
        self.addCleanup(self._patch.stop)
        self.addCleanup(
            lambda: os.path.exists(self.db_path) and os.unlink(self.db_path)
        )

    def _user_version(self):
        conn = sqlite3.connect(self.db_path)
        try:
            return conn.execute("PRAGMA user_version").fetchone()[0]
        finally:
            conn.close()

    def _set_user_version(self, value):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(f"PRAGMA user_version = {int(value)}")
            conn.commit()
        finally:
            conn.close()


class SchemaVersionMarkerTest(_TempProfile):
    def test_fresh_database_carries_the_current_generation(self):
        from database.init_db import initialize_database

        initialize_database()
        self.assertEqual(self._user_version(), SCHEMA_VERSION)

    def test_marker_is_positive(self):
        """0 "işaret yok" ile aynı şey — kuşak numarası 0 OLAMAZ."""
        self.assertGreater(SCHEMA_VERSION, 0)

    def test_legacy_zero_database_is_migrated_and_marked(self):
        """Sahadaki bütün profiller 0 taşıyor; göç edip işaret almalılar."""
        from database.init_db import initialize_database

        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, name TEXT, "
                     "type TEXT, balance REAL)")
        conn.commit()
        conn.close()
        self.assertEqual(self._user_version(), 0)

        initialize_database()
        self.assertEqual(self._user_version(), SCHEMA_VERSION)

    def test_marker_is_idempotent(self):
        from database.init_db import initialize_database

        initialize_database()
        initialize_database()
        self.assertEqual(self._user_version(), SCHEMA_VERSION)

    def test_equal_version_opens_normally(self):
        """Kendi kuşağı reddedilmemeli — aksi hâlde hiçbir profil açılmazdı."""
        from database.init_db import initialize_database

        initialize_database()
        initialize_database()

    def test_marker_is_not_written_when_setup_fails_midway(self):
        """Yarım kalan kurulum kendini "tamamlandı" diye işaretlemez."""
        from database.init_db import initialize_database
        from tests.test_connection_ownership_contract import (
            _InjectedFailure, _failing_connection,
        )

        with _failing_connection("database.init_db", fail_after=6):
            with self.assertRaises(_InjectedFailure):
                initialize_database()
        self.assertEqual(self._user_version(), 0,
                         "yarım kurulum kuşak işaretini koymamalı")


class DowngradeIsRefusedTest(_TempProfile):
    def test_newer_database_is_refused(self):
        from database.init_db import initialize_database

        initialize_database()
        self._set_user_version(SCHEMA_VERSION + 1)

        with self.assertRaises(SchemaTooNewError) as ctx:
            initialize_database()
        self.assertEqual(ctx.exception.found, SCHEMA_VERSION + 1)
        self.assertEqual(ctx.exception.supported, SCHEMA_VERSION)

    def test_refusal_is_catchable_as_a_migration_error(self):
        """Mevcut hata sınırları yeni tipi zaten tanımalı."""
        self.assertTrue(issubclass(SchemaTooNewError, DataMigrationError))

    def test_refused_database_is_left_untouched(self):
        """ASIL İDDİA: reddedilen profile HİÇ yazılmamalı."""
        from database.init_db import initialize_database
        from services.account_service import AccountService

        initialize_database()
        account_id = AccountService.create_account("Dokunma", "checking", 4321.0)
        self._set_user_version(SCHEMA_VERSION + 5)

        conn = sqlite3.connect(self.db_path)
        try:
            before = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master"
            ).fetchone()[0]
            balance_before = conn.execute(
                "SELECT balance FROM accounts WHERE id=?", (account_id,)
            ).fetchone()[0]
        finally:
            conn.close()

        with self.assertRaises(SchemaTooNewError):
            initialize_database()

        conn = sqlite3.connect(self.db_path)
        try:
            after = conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0]
            balance_after = conn.execute(
                "SELECT balance FROM accounts WHERE id=?", (account_id,)
            ).fetchone()[0]
            still = conn.execute("PRAGMA user_version").fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(after, before, "reddedilen DB'de şema değişti")
        self.assertEqual(balance_after, balance_before, "reddedilen DB'de bakiye değişti")
        self.assertEqual(still, SCHEMA_VERSION + 5,
                         "reddedilen DB'nin kuşak işareti geri alındı")

    def test_refusal_closes_its_connection(self):
        """Reddetme yolu da bağlantı bırakmamalı — Windows'ta kilit demek."""
        from database.init_db import initialize_database
        from tests.test_connection_ownership_contract import connection_ledger

        initialize_database()
        self._set_user_version(SCHEMA_VERSION + 1)

        with connection_ledger() as ledger:
            with self.assertRaises(SchemaTooNewError):
                initialize_database()
        self.assertEqual(ledger.leaked, [])


class UserMessageIsSafeTest(unittest.TestCase):
    """Kullanıcı metni bir sızıntı yüzeyi olmamalı (P1-1 ile aynı sözleşme)."""

    def test_message_leaks_no_version_path_or_exception_detail(self):
        text = SCHEMA_TOO_NEW_MESSAGE
        self.assertNotIn(str(SCHEMA_VERSION), text)
        for forbidden in ("Traceback", "PRAGMA", "user_version", "sqlite",
                          ".db", "/", "\\"):
            self.assertNotIn(forbidden, text, f"kullanıcı metninde {forbidden!r}")

    def test_message_tells_the_user_their_data_is_intact(self):
        """Metin, verinin korunduğunu SÖYLEMELİ — asıl kaygı bu."""
        self.assertIn("dokunulmadı", SCHEMA_TOO_NEW_MESSAGE)

    def test_presenter_receives_the_fixed_message(self):
        """Sunucu fonksiyona exception metni değil sabit metin geçilmeli."""
        from services import startup_recovery

        captured = {}

        class _Dialog:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def open(self):
                captured["opened"] = True


        scheduled = []

        class _App:
            pass

        class _StandIn:
            """Pencere gerektirmeyen widget karşılığı.

            `Widget.__init__` `EventLoop.ensure_window()` çağırıyor ve
            pencere sağlayıcısı olmayan başsız testte bu `sys.exit(1)`
            yapıyor; bu testin konusu widget çizimi değil, metin sözleşmesi.
            """

            def __init__(self, **kwargs):
                self.children = []
                for name, value in kwargs.items():
                    setattr(self, name, value)

            def add_widget(self, widget):
                self.children.append(widget)

            def bind(self, **kwargs):
                pass

        app = _App()
        with mock.patch.dict(
            "sys.modules",
            {"kivymd.uix.dialog": mock.Mock(MDDialog=_Dialog)},
        ), mock.patch("kivy.uix.boxlayout.BoxLayout", _StandIn),                 mock.patch("kivy.uix.label.Label", _StandIn):
            root = startup_recovery.present_startup_failure(
                app, startup_recovery.SCHEMA_TOO_NEW_TITLE,
                SCHEMA_TOO_NEW_MESSAGE, schedule=scheduled.append,
            )
            self.assertIsNotNone(root, "güvenli root dönmedi")
            self.assertEqual(len(scheduled), 1, "diyalog ertelenmedi")
            scheduled[0]()

        self.assertEqual(captured["text"], SCHEMA_TOO_NEW_MESSAGE)
        self.assertTrue(captured["opened"])
        self.assertEqual(app._startup_recovery_failure, SCHEMA_TOO_NEW_MESSAGE)


if __name__ == "__main__":
    unittest.main()
