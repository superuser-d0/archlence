"""Birikim hedeflerinin kalıcı kimliği ve göç yardımcı tabloları (dilim 1).

Bu paket ŞEMANIN kendisini sabitler; göç motorunu değil. Sabitlenen şeyler:

  * `goal_uid` hem taze kurulumda hem GÖÇ EDEN eski profilde var ve dolu,
  * backfill idempotent — ikinci koşum var olan hiçbir UID'yi değiştirmiyor,
  * `UNIQUE` index gerçekten kurulu,
  * aynı ad ve tutara sahip iki meşru hedef AYRI UID alıyor (deterministik
    türetme kullanılmadığının kanıtı),
  * karantina ve işaret tabloları mevcut,
  * kuşak işareti 2.

`goal_uid` neden gerekiyor: sayısal `id` restore'dan sonra yeniden
kullanılabiliyor (tests/test_savings_identity_reuse_regression.py).
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# `savings_goals`'ın v0.0.12 kuşağındaki hâli — göç edecek profilin şeması.
LEGACY_SAVINGS_TABLE = """
    CREATE TABLE savings_goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal_name TEXT NOT NULL,
        target_amount REAL NOT NULL,
        current_amount REAL DEFAULT 0,
        target_date TEXT,
        status TEXT DEFAULT 'aktif'
    )
"""

NEW_GOAL_COLUMNS = ("goal_uid", "color", "auto_deposit", "created_at")


class _Profile(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patch = mock.patch("database.db.DB_NAME", self.db_path)
        self._patch.start()
        self.addCleanup(self._patch.stop)
        self.addCleanup(
            lambda: os.path.exists(self.db_path) and os.unlink(self.db_path)
        )

    def _columns(self, table="savings_goals"):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]

    def _tables(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }

    def _uids(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return {
                row[0]: row[1] for row in conn.execute(
                    "SELECT id, goal_uid FROM savings_goals ORDER BY id"
                )
            }

    def _seed_legacy_profile(self, goals):
        """Yeni sütunları HİÇ bilmeyen bir profil kurar."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(LEGACY_SAVINGS_TABLE)
            conn.executemany(
                "INSERT INTO savings_goals(id, goal_name, target_amount,"
                " current_amount, target_date, status)"
                " VALUES(?,?,?,?,?,?)",
                goals,
            )
            conn.commit()


class FreshProfileTest(_Profile):
    def test_fresh_profile_has_every_new_column(self):
        from database.init_db import initialize_database

        initialize_database()
        columns = self._columns()
        for column in NEW_GOAL_COLUMNS:
            self.assertIn(column, columns)

    def test_new_columns_are_appended_in_a_fixed_order(self):
        """Taze CREATE TABLE ile ALTER zinciri AYNI sırayı üretmeli.

        `scripts/audit/check_schema_consistency.py` taze ve göç etmiş şemayı
        sütun sütun karşılaştırıyor; sıra farkı, gerçek bir uyumsuzluk
        olmadan kapıyı kırardı.
        """
        from database.init_db import initialize_database

        initialize_database()
        self.assertEqual(self._columns()[-4:], list(NEW_GOAL_COLUMNS))

    def test_helper_tables_exist(self):
        from database.init_db import initialize_database

        initialize_database()
        tables = self._tables()
        self.assertIn("savings_migration_quarantine", tables)
        self.assertIn("savings_migration_state", tables)

    def test_generation_marker_is_two(self):
        from database.init_db import SCHEMA_VERSION, initialize_database

        initialize_database()
        with closing(sqlite3.connect(self.db_path)) as conn:
            found = conn.execute("PRAGMA user_version").fetchone()[0]
        self.assertEqual(found, 2)
        self.assertEqual(SCHEMA_VERSION, 2)


class LegacyProfileUpgradeTest(_Profile):
    def setUp(self):
        super().setUp()
        self._seed_legacy_profile([
            (1, "sifreli-1", 20000.0, 1000.0, "2026-06-01", "aktif"),
            (2, "sifreli-2", 5000.0, 0.0, None, "aktif"),
        ])

    def test_upgrade_adds_columns_in_the_same_order_as_a_fresh_profile(self):
        from database.init_db import initialize_database

        initialize_database()
        self.assertEqual(self._columns()[-4:], list(NEW_GOAL_COLUMNS))

    def test_every_existing_row_is_backfilled_with_a_distinct_uid(self):
        from database.init_db import initialize_database

        initialize_database()
        uids = self._uids()
        self.assertEqual(set(uids), {1, 2})
        self.assertTrue(all(uids.values()), "backfill boş UID bırakamaz")
        self.assertEqual(len(set(uids.values())), 2, "UID'ler benzersiz olmalı")

    def test_backfill_never_rewrites_an_existing_uid(self):
        """İDEMPOTENLİK. UID değişirse yedeklerdeki bağ kopar."""
        from database.init_db import initialize_database

        initialize_database()
        first = self._uids()
        initialize_database()
        initialize_database()
        self.assertEqual(self._uids(), first)

    def test_amounts_are_untouched_by_the_schema_step(self):
        from database.init_db import initialize_database

        initialize_database()
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT id, target_amount, current_amount FROM savings_goals"
                " ORDER BY id"
            ).fetchall()
        self.assertEqual(rows, [(1, 20000.0, 1000.0), (2, 5000.0, 0.0)])

    def test_auto_deposit_defaults_to_false_for_existing_rows(self):
        from database.init_db import initialize_database

        initialize_database()
        with closing(sqlite3.connect(self.db_path)) as conn:
            values = [
                row[0] for row in conn.execute(
                    "SELECT auto_deposit FROM savings_goals ORDER BY id"
                )
            ]
        self.assertEqual(values, [0, 0])


class UidUniquenessTest(_Profile):
    def setUp(self):
        super().setUp()
        from database.init_db import initialize_database

        initialize_database()

    def test_unique_index_is_installed(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            indexes = {
                row[1]: row[2]
                for row in conn.execute("PRAGMA index_list(savings_goals)")
            }
        self.assertIn("idx_savings_goals_uid", indexes)
        self.assertEqual(indexes["idx_savings_goals_uid"], 1, "index UNIQUE olmalı")

    def test_duplicate_uid_is_rejected_by_the_database(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO savings_goals(goal_name, target_amount, goal_uid)"
                " VALUES('a', 1, 'ayni-uid')"
            )
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO savings_goals(goal_name, target_amount, goal_uid)"
                    " VALUES('b', 1, 'ayni-uid')"
                )

    def test_two_legitimate_goals_with_the_same_name_and_amount_differ(self):
        """Ad+tutar KİMLİK DEĞİLDİR — iki "Eğitim, 50.000" meşrudur."""
        from services.savings_service import SavingsService

        first = SavingsService.create_goal("Eğitim", 50000.0)
        second = SavingsService.create_goal("Eğitim", 50000.0)
        goals = {g["id"]: g for g in SavingsService.get_goals()}
        self.assertNotEqual(goals[first]["goal_uid"], goals[second]["goal_uid"])


class ServiceContractTest(_Profile):
    def setUp(self):
        super().setUp()
        from database.init_db import initialize_database

        initialize_database()

    def test_created_goal_carries_a_uid_and_the_new_fields(self):
        from services.savings_service import SavingsService

        goal_id = SavingsService.create_goal(
            "Tatil Fonu", 10000.0, "2026-08-01",
            color="blue", auto_deposit=True, created_at="2026-01-05",
        )
        goal = next(
            g for g in SavingsService.get_goals() if g["id"] == goal_id
        )
        self.assertTrue(goal["goal_uid"])
        self.assertEqual(goal["color"], "blue")
        self.assertIs(goal["auto_deposit"], True)
        self.assertEqual(goal["created_at"], "2026-01-05")

    def test_defaults_are_conservative(self):
        from services.savings_service import SavingsService

        goal_id = SavingsService.create_goal("Acil Durum", 1000.0)
        goal = next(
            g for g in SavingsService.get_goals() if g["id"] == goal_id
        )
        self.assertIs(goal["auto_deposit"], False)
        self.assertIsNone(goal["color"])
        self.assertTrue(goal["created_at"], "created_at boş bırakılmamalı")

    def test_deposit_result_carries_the_same_shape_as_the_list(self):
        """Tek işlemden dönen sözlük ile listedeki sözlük ayrışmamalı."""
        from services.account_service import AccountService
        from services.savings_service import SavingsService

        account_id = AccountService.create_account(
            "Vadesiz", "checking", initial_balance=1000.0
        )
        goal_id = SavingsService.create_goal("Araba", 5000.0, color="green")
        updated = SavingsService.deposit_to_goal(goal_id, 100.0, account_id)
        listed = next(
            g for g in SavingsService.get_goals() if g["id"] == goal_id
        )
        self.assertEqual(set(updated), set(listed))
        self.assertEqual(updated["goal_uid"], listed["goal_uid"])
        self.assertEqual(updated["color"], "green")


if __name__ == "__main__":
    unittest.main()
