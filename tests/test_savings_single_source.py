"""Arayüz/servis sınırı: hedefler yalnız SQL'den besleniyor (dilim 3).

Sabitlenen sözleşme (docs/ARCHITECTURE.md):

  * `main.py` hedefleri `JsonStore` üzerinden OKUMUYOR,
  * `SavingsMixin` listeyi `SavingsService.get_goals()`'tan alıyor,
  * oluşturma/yatırma/silme TEK servis sınırında bitiyor ve SQL commit'inden
    sonra ZORUNLU bir JSON yazımı KALMADI,
  * her kart işlemi `goal_uid` ile doğrulanıyor; sayısal id tek başına
    kullanıcı eyleminin hedefini kanıtlamıyor,
  * servis, verilen `goal_uid` satırla eşleşmiyorsa fail-closed reddediyor,
  * kullanıcıya traceback değil anlaşılır metin gidiyor.
"""

import ast
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _Ids(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class _Profile(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.db_path = self.root / "finance.db"
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

    def make_app(self):
        from mixins.savings_mixin import SavingsMixin

        class _App(SavingsMixin):
            pass

        app = _App()
        app.savings_goals = []
        app.root = None
        return app

    def balance(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return conn.execute(
                "SELECT balance FROM accounts WHERE id = ?", (self.account_id,)
            ).fetchone()[0]

    def ledger_rows(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM balance_events"
            ).fetchone()[0]


class SourceOfTruthTest(_Profile):
    def test_loading_reads_from_sql_not_from_a_json_store(self):
        from services.savings_service import SavingsService

        SavingsService.create_goal("Araba Fonu", 20000.0, color="green")
        app = self.make_app()
        # `store` HİÇ verilmiyor: JSON'a dokunan bir kod yolu kalsaydı
        # AttributeError ile patlardı.
        goals = app.load_savings_goals()

        self.assertEqual([g["name"] for g in goals], ["Araba Fonu"])
        self.assertTrue(goals[0]["goal_uid"])
        self.assertEqual(goals[0]["color"], "green")

    def test_the_view_carries_the_identity_fields(self):
        from services.savings_service import SavingsService

        goal_id = SavingsService.create_goal("Tatil Fonu", 10000.0)
        app = self.make_app()
        goal = app.load_savings_goals()[0]

        self.assertEqual(goal["id"], goal_id)
        self.assertTrue(goal["goal_uid"])

    def test_main_no_longer_reads_goals_through_jsonstore(self):
        """Kaynak seviyesinde kanıt: `build()` içinde JSON okuması yok.

        Davranış testi bunu yakalayamazdı — okuma geri gelse bile SQL yolu
        çalışmaya devam eder ve test yeşil kalırdı.
        """
        source = Path(__file__).resolve().parents[1] / "main.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        build = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "build"
        )
        jsonstore_targets = [
            node for node in ast.walk(build)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "JsonStore"
            and any(
                isinstance(arg, ast.Call)
                and getattr(arg.func, "id", "") == "_resolve_savings_store_path"
                for arg in node.args
            )
        ]
        self.assertEqual(
            jsonstore_targets, [],
            "build() birikim hedeflerini yine JsonStore'dan okuyor",
        )

    def test_no_module_writes_the_savings_json_any_more(self):
        """`self.store.put('goals', ...)` çağrısı hiçbir yerde kalmamalı."""
        root = Path(__file__).resolve().parents[1]
        offenders = []
        for path in [root / "main.py", *(root / "mixins").glob("*.py")]:
            text = path.read_text(encoding="utf-8")
            if "store.put('goals'" in text or 'store.put("goals"' in text:
                offenders.append(path.name)
        self.assertEqual(offenders, [])


class CreateFlowTest(_Profile):
    def test_creating_a_goal_persists_every_field_in_sql(self):
        app = self.make_app()
        app.sg_target_input = SimpleNamespace(text="15000")
        app.sg_name_input = SimpleNamespace(text="Ev Fonu")
        app.sg_auto_deposit = True
        app.sg_dialog = SimpleNamespace(dismiss=lambda: None)
        app.safe_refresh_charts = lambda: None

        with mock.patch("mixins.savings_mixin.toast"):
            app.commit_savings_goal()

        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT goal_uid, color, auto_deposit, created_at,"
                " target_amount FROM savings_goals"
            ).fetchone()
        self.assertTrue(row["goal_uid"])
        self.assertEqual(row["color"], "green")
        self.assertEqual(row["auto_deposit"], 1)
        self.assertTrue(row["created_at"])
        self.assertEqual(row["target_amount"], 15000.0)
        self.assertEqual(app.savings_goals[0]["name"], "Ev Fonu")


class IdentityVerifiedOperationsTest(_Profile):
    def setUp(self):
        super().setUp()
        from services.savings_service import SavingsService

        self.goal_id = SavingsService.create_goal("Araba Fonu", 20000.0)
        self.app = self.make_app()
        self.goal = self.app.load_savings_goals()[0]

    def test_a_deposit_with_the_matching_uid_succeeds(self):
        updated = self.app.deposit_into_goal(self.goal, 250.0, self.account_id)
        self.assertEqual(updated["current_amount"], 250.0)
        self.assertEqual(self.balance(), 4750.0)
        self.assertEqual(self.app.savings_goals[0]["current"], 250.0)

    def test_a_deposit_with_a_foreign_uid_is_refused_before_money_moves(self):
        stale = dict(self.goal, goal_uid="baska-bir-hedefin-kimligi")
        before, ledger = self.balance(), self.ledger_rows()

        with self.assertRaises(ValueError) as caught:
            self.app.deposit_into_goal(stale, 250.0, self.account_id)

        self.assertEqual(self.balance(), before)
        self.assertEqual(self.ledger_rows(), ledger)
        self.assertNotIn("Traceback", str(caught.exception))

    def test_a_card_without_a_uid_never_reaches_the_service(self):
        """Kimliği kanıtlanamayan kart servise HİÇ gitmemeli."""
        from services.savings_service import SavingsService

        card = {"id": self.goal_id, "name": "Araba Fonu", "target": 20000.0}
        with mock.patch.object(SavingsService, "deposit_to_goal") as spy:
            with self.assertRaises(ValueError):
                self.app.deposit_into_goal(card, 100.0, self.account_id)
        spy.assert_not_called()

    def test_the_service_itself_refuses_a_mismatched_uid(self):
        """İki katman: mixin geçse bile servis kendi tarafında reddeder."""
        from services.savings_service import SavingsService

        before = self.balance()
        with self.assertRaises(ValueError):
            SavingsService.deposit_to_goal(
                self.goal_id, 100.0, self.account_id, goal_uid="uydurma"
            )
        self.assertEqual(self.balance(), before)

    def test_withdraw_and_delete_share_the_same_fail_closed_contract(self):
        from services.savings_service import SavingsService

        SavingsService.deposit_to_goal(self.goal_id, 300.0, self.account_id)
        before = self.balance()

        with self.assertRaises(ValueError):
            SavingsService.withdraw_from_goal(
                self.goal_id, 100.0, self.account_id, goal_uid="uydurma"
            )
        with self.assertRaises(ValueError):
            SavingsService.delete_goal(
                self.goal_id, self.account_id, goal_uid="uydurma"
            )

        self.assertEqual(self.balance(), before)
        self.assertEqual(len(self.app.load_savings_goals()), 1)

    def test_deleting_through_the_card_refunds_and_refreshes_from_sql(self):
        from services.savings_service import SavingsService

        SavingsService.deposit_to_goal(self.goal_id, 400.0, self.account_id)
        goal = self.app.load_savings_goals()[0]

        deleted = self.app.delete_goal_record(
            goal, self.account_id, refund=True
        )

        self.assertTrue(deleted)
        self.assertEqual(self.app.savings_goals, [])
        self.assertEqual(self.balance(), 5000.0)

    def test_operations_do_not_leave_a_json_file_behind(self):
        self.app.deposit_into_goal(self.goal, 100.0, self.account_id)
        self.assertFalse((self.root / "savings_goals.json").exists())


class UnreadableGoalsTest(_Profile):
    def test_a_missing_key_is_reported_as_unreadable_not_as_empty(self):
        from services.savings_service import SavingsService
        from utils.errors import KeyUnavailableError

        SavingsService.create_goal("Araba Fonu", 20000.0)
        app = self.make_app()

        with mock.patch(
            "utils.crypto._get_aead_key",
            side_effect=KeyUnavailableError("anahtar yok"),
        ):
            goals = app.load_savings_goals()

        self.assertEqual(goals, [])
        self.assertTrue(app._savings_unavailable)


class StartupMigrationWiringTest(_Profile):
    """Açılış sırası: göç -> SQL'den okuma."""

    def test_startup_migrates_a_legacy_profile_and_shows_its_goals(self):
        import json

        import main as archlence_main

        legacy = self.root / "savings_goals.json"
        legacy.write_text(
            json.dumps({"goals": {"data": [
                {"id": 1, "name": "Araba Fonu", "target": 20000.0,
                 "current": 0.0, "color": "green", "auto_deposit": False,
                 "created_at": "2026-01-02"},
            ]}}),
            encoding="utf-8",
        )

        app = self.make_app()
        app._run_savings_migration_at_startup = (
            archlence_main.ArchlenceApp._run_savings_migration_at_startup.__get__(app)
        )
        with mock.patch.object(
            archlence_main, "_resolve_savings_store_path",
            return_value=str(legacy),
        ):
            app._run_savings_migration_at_startup()
        goals = app.load_savings_goals()

        self.assertEqual([g["name"] for g in goals], ["Araba Fonu"])
        self.assertFalse(legacy.exists(), "JSON emekliye ayrılmalı")
        self.assertTrue(list(self.root.glob("savings_goals.json.migrated-*")))

    def test_a_migration_failure_does_not_stop_startup(self):
        import main as archlence_main
        from services import savings_migration

        app = self.make_app()
        app._run_savings_migration_at_startup = (
            archlence_main.ArchlenceApp._run_savings_migration_at_startup.__get__(app)
        )
        with mock.patch.object(
            savings_migration, "run_savings_migration",
            side_effect=OSError("disk hatası"),
        ):
            self.assertIsNone(app._run_savings_migration_at_startup())


class QuarantineNotificationTest(_Profile):
    """Karantina bildirimi SESSİZ LOGLA SINIRLI KALMAMALI.

    Otomatik taşınamayan bir hedefi yalnız log'a yazmak, düzeltmeye
    çalıştığımız kusurun (sessiz yanlış atıf) sessiz kardeşi olurdu:
    kullanıcı bir hedefinin ekranda görünmediğini fark etmezdi.
    """

    def _quarantine_a_record(self):
        import json

        from services.savings_migration import run_savings_migration

        legacy = self.root / "savings_goals.json"
        legacy.write_text(
            json.dumps({"goals": {"data": [
                # SQL'de karşılığı yok ve üzerinde para var -> karantina.
                {"id": 4242, "name": "Kayıp Fon", "target": 9000.0,
                 "current": 4500.0},
            ]}}),
            encoding="utf-8",
        )
        run_savings_migration(json_path=legacy, db_path=self.db_path)

    def _present(self):
        """Bildirimi GERÇEK `main.py` koduyla çalıştırır, widget kurmadan.

        KivyMD düğmeleri çalışan bir `MDApp` istiyor; bu test bildirimin
        İÇERİĞİNİ ve kapanış sözleşmesini ölçüyor, KivyMD'nin kendisini değil.
        """
        import main as archlence_main

        captured = {}

        class _Dialog:
            def __init__(self, **kwargs):
                captured.update(kwargs)
                self.on_dismiss_handlers = []
                captured["dialog"] = self

            def bind(self, **kwargs):
                self.on_dismiss_handlers.append(kwargs["on_dismiss"])

            def open(self):
                captured["opened"] = True

            def dismiss(self):
                for handler in self.on_dismiss_handlers:
                    handler(self)

        app = self.make_app()
        app.theme_cls = mock.Mock()
        with mock.patch.dict(
            "sys.modules",
            {"kivymd.uix.dialog": mock.Mock(MDDialog=_Dialog)},
        ), mock.patch.object(
            archlence_main.ftheme, "primary_button",
            side_effect=lambda *a, **k: mock.Mock(),
        ):
            archlence_main.ArchlenceApp._present_savings_quarantine(app)
        return captured

    def test_the_user_is_shown_which_goals_could_not_be_migrated(self):
        self._quarantine_a_record()

        captured = self._present()

        self.assertTrue(captured.get("opened"), "diyalog açılmadı")
        self.assertIn("Kayıp Fon", captured["text"])
        self.assertNotIn("Traceback", captured["text"])
        self.assertNotIn(str(self.db_path), captured["text"])

    def test_dismissing_the_dialog_acknowledges_but_keeps_the_records(self):
        from services import savings_migration

        self._quarantine_a_record()
        captured = self._present()

        self.assertEqual(
            len(savings_migration.pending_quarantine(self.db_path)), 1,
            "kapanıştan önce kayıt hâlâ bekliyor olmalı",
        )
        captured["dialog"].dismiss()

        self.assertEqual(
            savings_migration.pending_quarantine(self.db_path), [],
            "kapanış bildirimi 'gösterildi' diye işaretlemeli",
        )
        with closing(sqlite3.connect(self.db_path)) as conn:
            kept = conn.execute(
                "SELECT COUNT(*) FROM savings_migration_quarantine"
            ).fetchone()[0]
        self.assertEqual(kept, 1, "bildirim gösterildi diye kayıt silinemez")

    def test_a_clean_profile_shows_no_dialog(self):
        self.assertNotIn("opened", self._present())


if __name__ == "__main__":
    unittest.main()
