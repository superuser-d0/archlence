"""JSON -> SQLite göç motorunun sözleşmesi (dilim 2).

`services/savings_migration.py` modül docstring'indeki her madde burada ayrı
bir testle sabitleniyor. Testler GERÇEK SQLite dosyalarıyla ve gerçek şifreleme
yoluyla koşuyor; sınıflandırma mantığının saf kısmı ayrıca veritabanısız
sınanıyor.

Kapsanan matris (plan §10): temiz profil, yalnız-JSON, yalnız-SQL, tam
eşleşme, kısmi ayrışma, aynı id farklı hedef, aynı hedef farklı id, aynı
ad+tutarda iki meşru hedef, tek yönlü eksikler, bozuk JSON, anahtarsız profil,
iki ve üç kez koşum, her aşamada kesinti enjeksiyonu, finansal değişmezler.
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import savings_migration as migration
from services.savings_migration import (
    DECISION_INSERT,
    DECISION_MATCH,
    DECISION_QUARANTINE,
    MIGRATION_MARKER,
    REASON_AMBIGUOUS,
    REASON_DUPLICATE_ID,
    REASON_ID_COLLISION,
    REASON_STALE_JSON,
    REASON_UNMATCHED_WITH_BALANCE,
    REASON_UNREADABLE_FILE,
    SavingsMigrationError,
    classify,
    run_savings_migration,
)
from utils.errors import KeyUnavailableError


def _record(legacy_id, name, target=1000.0, current=0.0, color=None,
            auto_deposit=False, created_at=None):
    return {
        "legacy_id": legacy_id, "name": name, "target": target,
        "current": current, "color": color, "auto_deposit": auto_deposit,
        "created_at": created_at,
    }


def _existing(goal_id, name, target=1000.0, current=0.0):
    return {
        "id": goal_id, "goal_uid": f"uid-{goal_id}", "name": name,
        "target": target, "current": current, "color": None,
        "auto_deposit": 0, "created_at": None,
    }


class ClassificationTest(unittest.TestCase):
    """Karar tablosunun SAF hâli — veritabanı yok, yalnız mantık."""

    def test_id_and_name_together_are_a_match(self):
        decisions = classify(
            [_record(1, "Tatil Fonu")], [_existing(1, "Tatil Fonu")]
        )
        self.assertEqual(decisions[0][0], DECISION_MATCH)

    def test_same_id_different_name_is_quarantined(self):
        decisions = classify(
            [_record(2, "Tatil Fonu")], [_existing(2, "Yeni Hedef")]
        )
        self.assertEqual(decisions[0][0], DECISION_QUARANTINE)
        self.assertEqual(decisions[0][2], REASON_ID_COLLISION)

    def test_same_name_and_amount_under_a_different_id_is_quarantined(self):
        """Ad+tutar KANIT DEĞİL: ne birleştir ne ikiye böl."""
        decisions = classify(
            [_record(7, "Eğitim", 50000.0)],
            [_existing(3, "Eğitim", 50000.0)],
        )
        self.assertEqual(decisions[0][0], DECISION_QUARANTINE)
        self.assertEqual(decisions[0][2], REASON_AMBIGUOUS)

    def test_two_legitimate_goals_with_the_same_name_are_both_matched(self):
        """İkisi de kendi id'siyle tutuyorsa ikisi de meşrudur; birleşmezler."""
        decisions = classify(
            [_record(1, "Eğitim", 50000.0), _record(2, "Eğitim", 50000.0)],
            [_existing(1, "Eğitim", 50000.0), _existing(2, "Eğitim", 50000.0)],
        )
        self.assertEqual([d[0] for d in decisions],
                         [DECISION_MATCH, DECISION_MATCH])

    def test_duplicate_id_inside_the_json_quarantines_both(self):
        decisions = classify(
            [_record(4, "A"), _record(4, "B")], []
        )
        self.assertEqual([d[2] for d in decisions],
                         [REASON_DUPLICATE_ID, REASON_DUPLICATE_ID])

    def test_unmatched_record_without_money_is_inserted(self):
        decisions = classify([_record(9, "Yeni", 500.0, 0.0)], [])
        self.assertEqual(decisions[0][0], DECISION_INSERT)

    def test_unmatched_record_carrying_money_is_quarantined(self):
        """Karşılıksız para YOKTAN VAR EDİLMEZ."""
        decisions = classify([_record(9, "Yeni", 500.0, 120.0)], [])
        self.assertEqual(decisions[0][0], DECISION_QUARANTINE)
        self.assertEqual(decisions[0][2], REASON_UNMATCHED_WITH_BALANCE)

    def test_sql_only_goal_produces_no_decision(self):
        self.assertEqual(classify([], [_existing(1, "Sadece SQL")]), [])


class _MigrationProfile(unittest.TestCase):
    """Gerçek dosyalar: finance.db + savings_goals.json."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.db_path = self.root / "finance.db"
        self.json_path = self.root / "savings_goals.json"
        self.key = os.urandom(32)

        self._db_patch = mock.patch("database.db.DB_NAME", str(self.db_path))
        self._db_patch.start()
        self.addCleanup(self._db_patch.stop)
        self._key_patch = mock.patch(
            "utils.crypto._get_aead_key", return_value=self.key
        )
        self._key_patch.start()
        self.addCleanup(self._key_patch.stop)

        from database.init_db import initialize_database
        from services.account_service import AccountService

        initialize_database()
        self.account_id = AccountService.create_account(
            "Vadesiz", "checking", initial_balance=5000.0
        )


    def write_json(self, goals):
        self.json_path.write_text(
            json.dumps({"goals": {"data": goals}}, ensure_ascii=False),
            encoding="utf-8",
        )

    def migrate(self, **kwargs):
        return run_savings_migration(
            json_path=self.json_path, db_path=self.db_path, **kwargs
        )

    def goals(self):
        from services.savings_service import SavingsService

        return SavingsService.get_goals()

    def by_name(self):
        return {goal["goal_name"]: goal for goal in self.goals()}

    def quarantine(self):
        return migration.pending_quarantine(self.db_path)

    def marker_rows(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return [
                row[0] for row in conn.execute(
                    "SELECT marker FROM savings_migration_state"
                )
            ]

    def financials(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return (
                conn.execute(
                    "SELECT COALESCE(SUM(balance), 0) FROM accounts"
                ).fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM balance_events").fetchone()[0],
                conn.execute(
                    "SELECT COALESCE(SUM(delta), 0) FROM balance_events"
                ).fetchone()[0],
            )

    def retired_files(self, suffix):
        return sorted(self.root.glob(f"savings_goals.json.{suffix}-*"))


class CleanProfileTest(_MigrationProfile):
    def test_no_json_is_a_no_op(self):
        result = self.migrate()
        self.assertEqual(result["status"], "no-json")
        self.assertNotIn(MIGRATION_MARKER, self.marker_rows())

    def test_sql_only_profile_is_untouched(self):
        from services.savings_service import SavingsService

        SavingsService.create_goal("Sadece SQL", 1000.0)
        before = self.financials()
        result = self.migrate()
        self.assertEqual(result["status"], "no-json")
        self.assertEqual([g["goal_name"] for g in self.goals()], ["Sadece SQL"])
        self.assertEqual(self.financials(), before)

    def test_empty_json_is_retired_without_inserting_anything(self):
        self.write_json([])
        result = self.migrate()
        self.assertEqual(result["status"], "empty")
        self.assertEqual(self.goals(), [])
        self.assertIn(MIGRATION_MARKER, self.marker_rows())
        self.assertFalse(self.json_path.exists())


class LegacyOnlyProfileTest(_MigrationProfile):
    """Yalnız eski JSON taşıyan desteklenen profil."""

    def setUp(self):
        super().setUp()
        self.write_json([
            {"id": 1, "name": "Araba Fonu", "target": 20000.0, "current": 0.0,
             "color": "green", "auto_deposit": False,
             "created_at": "2026-01-02"},
            {"id": 2, "name": "Tatil Fonu", "target": 10000.0, "current": 0.0,
             "color": "blue", "auto_deposit": True,
             "created_at": "2026-02-03"},
        ])

    def test_every_record_lands_in_sql_with_its_fields(self):
        result = self.migrate()
        self.assertEqual(result["status"], "migrated")
        self.assertEqual(result["inserted"], 2)

        goals = self.by_name()
        self.assertEqual(set(goals), {"Araba Fonu", "Tatil Fonu"})
        holiday = goals["Tatil Fonu"]
        self.assertEqual(holiday["target_amount"], 10000.0)
        self.assertEqual(holiday["color"], "blue")
        self.assertIs(holiday["auto_deposit"], True)
        self.assertEqual(holiday["created_at"], "2026-02-03")
        self.assertTrue(holiday["goal_uid"])

    def test_legacy_numeric_ids_are_preserved(self):
        """Eski id'yi korumak, aynı id'nin yeniden dağıtılmasını da önler."""
        self.migrate()
        goals = self.by_name()
        self.assertEqual(goals["Araba Fonu"]["id"], 1)
        self.assertEqual(goals["Tatil Fonu"]["id"], 2)

    def test_json_is_retired_not_deleted(self):
        result = self.migrate()
        self.assertFalse(self.json_path.exists())
        migrated = self.retired_files("migrated")
        self.assertEqual(len(migrated), 1)
        self.assertIn("Tatil Fonu", migrated[0].read_text(encoding="utf-8"))
        self.assertEqual(result["retired_path"], str(migrated[0]))

    def test_a_safety_snapshot_of_the_database_is_taken_first(self):
        result = self.migrate()
        snapshot = Path(result["safety_snapshot"])
        self.assertTrue(snapshot.exists())
        with closing(sqlite3.connect(snapshot)) as conn:
            rows = conn.execute("SELECT COUNT(*) FROM savings_goals").fetchone()[0]
        self.assertEqual(rows, 0, "yedek göç ÖNCESİ durumu taşımalı")

    def test_marker_is_written_and_journal_is_cleared(self):
        self.migrate()
        self.assertIn(MIGRATION_MARKER, self.marker_rows())
        self.assertIsNone(migration.read_journal(self.db_path))

    def test_financial_totals_do_not_move(self):
        before = self.financials()
        self.migrate()
        self.assertEqual(self.financials(), before)

    def test_running_it_three_times_changes_nothing(self):
        self.migrate()
        first = {g["goal_uid"]: g for g in self.goals()}
        financials = self.financials()

        second = self.migrate()
        third = self.migrate()

        self.assertEqual(second["status"], "no-json")
        self.assertEqual(third["status"], "no-json")
        self.assertEqual({g["goal_uid"]: g for g in self.goals()}, first)
        self.assertEqual(self.financials(), financials)


class MatchingProfileTest(_MigrationProfile):
    """JSON ve SQL'in birlikte yaşadığı gerçek durum."""

    def setUp(self):
        super().setUp()
        from services.savings_service import SavingsService

        self.goal_id = SavingsService.create_goal("Araba Fonu", 20000.0)
        SavingsService.deposit_to_goal(self.goal_id, 750.0, self.account_id)

    def _blank_legacy_fields(self, goal_id):
        """Satırı GERÇEK legacy hâline döndürür.

        Yeni `create_goal` artık color/created_at yazıyor; bu testin ölçtüğü
        şey ise eski kuşaktan gelen BOŞ alanların doldurulması. Alanları elle
        boşaltmasaydık test kendi kurduğu yeni satıra bakıp yanlış bir şeyi
        doğrulardı.
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "UPDATE savings_goals SET color = NULL, created_at = NULL,"
                " auto_deposit = 0 WHERE id = ?", (goal_id,)
            )
            conn.commit()

    def test_exact_match_completes_empty_fields_only(self):
        self._blank_legacy_fields(self.goal_id)
        self.write_json([{
            "id": self.goal_id, "name": "Araba Fonu", "target": 20000.0,
            "current": 999999.0,
            "color": "red", "auto_deposit": True, "created_at": "2025-12-01",
        }])
        result = self.migrate()

        goal = self.by_name()["Araba Fonu"]
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(result["completed"], 1)
        self.assertEqual(goal["current_amount"], 750.0, "SQL tutarı korunmalı")
        self.assertEqual(goal["color"], "red")
        self.assertIs(goal["auto_deposit"], True)
        self.assertEqual(goal["created_at"], "2025-12-01")

    def test_existing_field_values_are_never_overwritten(self):
        from services.savings_service import SavingsService

        other = SavingsService.create_goal(
            "Ev Fonu", 5000.0, color="green", created_at="2026-03-03"
        )
        self.write_json([{
            "id": other, "name": "Ev Fonu", "target": 5000.0, "current": 0.0,
            "color": "red", "auto_deposit": False, "created_at": "2020-01-01",
        }])
        self.migrate()

        goal = self.by_name()["Ev Fonu"]
        self.assertEqual(goal["color"], "green")
        self.assertEqual(goal["created_at"], "2026-03-03")

    def test_partial_divergence_mixes_decisions(self):
        self.write_json([
            {"id": self.goal_id, "name": "Araba Fonu", "target": 20000.0,
             "current": 750.0, "color": "green", "auto_deposit": False,
             "created_at": "2026-01-01"},
            {"id": 41, "name": "Yeni Hedef", "target": 1000.0, "current": 0.0,
             "color": "blue", "auto_deposit": False,
             "created_at": "2026-04-04"},
        ])
        result = self.migrate()

        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["quarantined"], 0)
        self.assertEqual(set(self.by_name()), {"Araba Fonu", "Yeni Hedef"})

    def test_sql_goal_missing_from_json_is_left_alone(self):
        self.write_json([])
        self.migrate()
        goal = self.by_name()["Araba Fonu"]
        self.assertEqual(goal["current_amount"], 750.0)

    def test_id_collision_is_quarantined_and_moves_no_money(self):
        self.write_json([{
            "id": self.goal_id, "name": "Tatil Fonu", "target": 10000.0,
            "current": 250.0, "color": "blue", "auto_deposit": False,
            "created_at": "2026-01-01",
        }])
        before = self.financials()
        result = self.migrate()

        self.assertEqual(result["quarantined"], 1)
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(self.financials(), before)
        self.assertEqual(self.by_name()["Araba Fonu"]["current_amount"], 750.0)

        quarantined = self.quarantine()
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(quarantined[0]["reason"], REASON_ID_COLLISION)
        self.assertEqual(quarantined[0]["goal_name"], "Tatil Fonu")
        self.assertTrue(quarantined[0]["message"])

    def test_quarantined_record_never_enters_the_financial_totals(self):
        self.write_json([{
            "id": 99, "name": "Kayıp Fon", "target": 9000.0, "current": 4500.0,
            "color": None, "auto_deposit": False, "created_at": None,
        }])
        before = self.financials()
        self.migrate()

        self.assertEqual(self.financials(), before)
        with closing(sqlite3.connect(self.db_path)) as conn:
            savings_total = conn.execute(
                "SELECT COALESCE(SUM(current_amount), 0) FROM savings_goals"
            ).fetchone()[0]
        self.assertEqual(savings_total, 750.0, "karantina tutarı toplama giremez")
        self.assertEqual(
            self.quarantine()[0]["reason"], REASON_UNMATCHED_WITH_BALANCE
        )

    def test_acknowledging_the_quarantine_hides_it_from_the_next_prompt(self):
        self.write_json([{
            "id": 99, "name": "Kayıp Fon", "target": 9000.0, "current": 4500.0,
        }])
        self.migrate()
        self.assertEqual(len(self.quarantine()), 1)

        migration.acknowledge_quarantine(self.db_path)
        self.assertEqual(self.quarantine(), [])

        with closing(sqlite3.connect(self.db_path)) as conn:
            kept = conn.execute(
                "SELECT COUNT(*) FROM savings_migration_quarantine"
            ).fetchone()[0]
        self.assertEqual(kept, 1, "bildirim gösterildi diye kayıt silinmemeli")


class UnreadableJsonTest(_MigrationProfile):
    def test_corrupt_json_stops_the_migration_without_partial_writes(self):
        self.json_path.write_text('{"goals": {"data": [', encoding="utf-8")
        result = self.migrate()

        self.assertEqual(result["status"], "unreadable-json")
        self.assertEqual(self.goals(), [])
        self.assertNotIn(MIGRATION_MARKER, self.marker_rows())
        self.assertEqual(self.quarantine()[0]["reason"], REASON_UNREADABLE_FILE)

    def test_the_unreadable_file_itself_is_preserved(self):
        self.json_path.write_text("bu json değil", encoding="utf-8")
        self.migrate()
        stored = self.retired_files("unreadable")
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].read_text(encoding="utf-8"), "bu json değil")

    def test_records_that_cannot_be_read_are_quarantined_individually(self):
        self.write_json([
            {"id": 1, "name": "Geçerli", "target": 100.0, "current": 0.0},
            {"id": 2, "name": "", "target": 100.0},
            "bu bir kayıt değil",
            {"id": 3, "name": "Negatif", "target": -5.0},
        ])
        result = self.migrate()

        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["quarantined"], 3)
        self.assertEqual([g["goal_name"] for g in self.goals()], ["Geçerli"])


class KeyUnavailableTest(_MigrationProfile):
    def test_migration_refuses_to_run_without_the_encryption_key(self):
        from services.savings_service import SavingsService

        SavingsService.create_goal("Araba Fonu", 20000.0)
        self.write_json([
            {"id": 1, "name": "Araba Fonu", "target": 20000.0, "current": 0.0},
        ])

        with mock.patch(
            "utils.crypto._get_aead_key",
            side_effect=KeyUnavailableError("anahtar yok"),
        ):
            result = self.migrate()

        self.assertEqual(result["status"], "key-unavailable")
        self.assertTrue(self.json_path.exists(), "JSON'a dokunulmamalı")
        self.assertNotIn(MIGRATION_MARKER, self.marker_rows())

    def test_the_next_run_with_a_key_completes_normally(self):
        self.write_json([
            {"id": 1, "name": "Araba Fonu", "target": 20000.0, "current": 0.0},
        ])
        with mock.patch(
            "utils.crypto._get_aead_key",
            side_effect=KeyUnavailableError("anahtar yok"),
        ):
            self.migrate()
        result = self.migrate()

        self.assertEqual(result["status"], "migrated")
        self.assertEqual(result["inserted"], 1)


class StaleJsonAfterRestoreTest(_MigrationProfile):
    """İşaret varken bulunan JSON tanım gereği BAYATTIR."""

    def setUp(self):
        super().setUp()
        self.write_json([
            {"id": 1, "name": "Araba Fonu", "target": 20000.0, "current": 0.0},
        ])
        self.migrate()

    def test_a_reappearing_json_is_quarantined_not_migrated(self):
        self.write_json([
            {"id": 1, "name": "Tatil Fonu", "target": 10000.0,
             "current": 500.0},
        ])
        before = self.financials()
        result = self.migrate()

        self.assertEqual(result["status"], "stale-json")
        self.assertEqual([g["goal_name"] for g in self.goals()], ["Araba Fonu"])
        self.assertEqual(self.financials(), before)
        self.assertEqual(self.quarantine()[0]["reason"], REASON_STALE_JSON)

    def test_the_stale_file_is_moved_aside_so_it_is_never_read_again(self):
        self.write_json([{"id": 1, "name": "Tatil Fonu", "target": 10000.0}])
        self.migrate()
        self.assertFalse(self.json_path.exists())
        self.assertEqual(len(self.retired_files("stale")), 1)


class FailureInjectionTest(_MigrationProfile):
    """Her kritik aşamada kesinti: yeniden koşum tamamlamalı, ikizlemiş
    olmamalı."""

    HOOKS = (
        "after_safety_snapshot",
        "after_invalid_records",
        "before_commit",
        "after_commit",
        "after_verification",
        "after_json_retired",
        "after_marker_written",
    )

    def setUp(self):
        super().setUp()
        self.write_json([
            {"id": 1, "name": "Araba Fonu", "target": 20000.0, "current": 0.0,
             "color": "green", "auto_deposit": False,
             "created_at": "2026-01-02"},
            {"id": 2, "name": "Tatil Fonu", "target": 10000.0, "current": 0.0,
             "color": "blue", "auto_deposit": True,
             "created_at": "2026-02-03"},
        ])

    def _inject(self, stage):
        class _Injected(RuntimeError):
            pass

        def hook(name):
            if name == stage:
                raise _Injected(stage)

        return _Injected, hook

    def test_every_stage_can_be_interrupted_and_retried(self):
        for stage in self.HOOKS:
            with self.subTest(stage=stage):
                self._reset_profile()
                injected, hook = self._inject(stage)
                try:
                    self.migrate(_failure_hook=hook)
                except injected:
                    pass


                self.migrate()

                goals = self.by_name()
                self.assertEqual(
                    sorted(goals), ["Araba Fonu", "Tatil Fonu"],
                    f"{stage} kesintisinden sonra hedefler eksik/fazla",
                )
                self.assertEqual(
                    len(self.goals()), 2, f"{stage} kesintisi kaydı ikizledi"
                )
                self.assertIn(MIGRATION_MARKER, self.marker_rows())

    def _reset_profile(self):
        """Her alt-test için taze bir profil."""
        for path in self.root.iterdir():
            if path.is_dir():
                continue
            path.unlink()
        from database.init_db import initialize_database
        from services.account_service import AccountService

        initialize_database()
        self.account_id = AccountService.create_account(
            "Vadesiz", "checking", initial_balance=5000.0
        )
        self.write_json([
            {"id": 1, "name": "Araba Fonu", "target": 20000.0, "current": 0.0,
             "color": "green", "auto_deposit": False,
             "created_at": "2026-01-02"},
            {"id": 2, "name": "Tatil Fonu", "target": 10000.0, "current": 0.0,
             "color": "blue", "auto_deposit": True,
             "created_at": "2026-02-03"},
        ])

    def test_a_crash_before_commit_leaves_no_rows_at_all(self):
        injected, hook = self._inject("before_commit")
        with self.assertRaises(injected):
            self.migrate(_failure_hook=hook)

        self.assertEqual(self.goals(), [])
        self.assertTrue(self.json_path.exists(), "JSON commit öncesi korunmalı")
        self.assertNotIn(MIGRATION_MARKER, self.marker_rows())

    def test_a_crash_after_commit_does_not_reinsert_on_retry(self):
        injected, hook = self._inject("after_commit")
        with self.assertRaises(injected):
            self.migrate(_failure_hook=hook)
        self.assertEqual(len(self.goals()), 2)

        uids_before = {g["goal_uid"] for g in self.goals()}
        result = self.migrate()

        self.assertEqual(len(self.goals()), 2, "yeniden koşum ikizledi")
        self.assertEqual({g["goal_uid"] for g in self.goals()}, uids_before)
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(result["skipped"], 2)


class VerificationTest(_MigrationProfile):
    def test_a_financial_drift_aborts_before_retirement(self):
        """Doğrulama kırmızıysa JSON emekliye AYRILMAZ, işaret YAZILMAZ."""
        self.write_json([
            {"id": 1, "name": "Araba Fonu", "target": 20000.0, "current": 0.0},
        ])
        real = migration._financial_fingerprint
        calls = {"n": 0}

        def drifting(conn):
            calls["n"] += 1
            snapshot = real(conn)
            if calls["n"] > 1:
                snapshot["accounts_total"] += 100.0
            return snapshot

        with mock.patch.object(
            migration, "_financial_fingerprint", side_effect=drifting
        ):
            with self.assertRaises(SavingsMigrationError):
                self.migrate()

        self.assertTrue(self.json_path.exists())
        self.assertNotIn(MIGRATION_MARKER, self.marker_rows())


if __name__ == "__main__":
    unittest.main()
