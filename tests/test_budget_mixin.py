"""Bütçe planlayıcının Araçlar-ızgarası mimarisi.

Panel `ui/dashboard.kv`'nin ortasından çıkarıldı; artık ızgarada tam genişlikte
DURMUYOR. Araçlar ızgarasındaki "Aylık Bütçe" karesi `show_budget_planner()`
ile paneli bir MDDialog içinde açar. Panel her açılışta yeniden örneklenip
`self._budget_planner_panel`'e konur; id'leri o örneğin `ids` sözlüğünde yaşar
(root.ids'te değil). Bu paket:
  * compute_budget_summary saf hesabını (widget'sız),
  * _planner_ids'in canlı panel referansı / root.ids fallback çözümlemesini
kilitler.

Kivy widget ağacı kurulmaz; `ids` sözlükleri stub'lanır.
"""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fixtures import AccountFixtureMixin


class _Ids(dict):
    """Kivy'nin ObservableDict'i gibi hem sözlük hem attribute erişimi verir."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _panel_stub():
    return SimpleNamespace(ids=_Ids(
        month_selector_container=SimpleNamespace(
            children=[], clear_widgets=lambda: None, add_widget=lambda w: None),
        projection_label=SimpleNamespace(text=""),
        projection_icon=SimpleNamespace(icon="", text_color=None),
        budget_detailed_list=SimpleNamespace(
            children=[], clear_widgets=lambda: None, add_widget=lambda w: None),
    ))


def _make_app():
    from mixins.budget_mixin import BudgetMixin

    class _App(BudgetMixin):
        pass

    app = _App()
    app.root = SimpleNamespace(ids=_Ids())
    return app


class PlannerIdResolutionTest(unittest.TestCase):
    """Panel diyaloğa taşındıktan sonra id çözümlemesi."""

    def test_resolved_through_live_panel_reference(self):
        app = _make_app()
        app._budget_planner_panel = _panel_stub()
        ids = app._planner_ids()
        self.assertIn("projection_label", ids)
        self.assertIn("month_selector_container", ids)

    def test_falls_back_to_root_ids_stray_panel(self):
        """Paneli KV'de sabit geri taşıyan biri için güvenli davranış."""
        app = _make_app()
        app.root.ids["budget_planner_panel"] = _panel_stub()
        ids = app._planner_ids()
        self.assertIn("projection_label", ids)

    def test_empty_when_no_panel_anywhere(self):
        """Diyalog kapalıyken (canlı panel yok) boş sözlük dönmeli."""
        app = _make_app()
        self.assertEqual(app._planner_ids(), {})

    def test_no_root_yields_empty_mapping(self):
        app = _make_app()
        app.root = None
        self.assertEqual(app._planner_ids(), {})

    def test_live_panel_beats_stray_root_panel(self):
        """Canlı diyalog paneli önceliklidir."""
        app = _make_app()
        live = _panel_stub()
        live.ids["projection_label"].text = "canlı"
        app._budget_planner_panel = live
        app.root.ids["budget_planner_panel"] = _panel_stub()
        self.assertEqual(app._planner_ids()["projection_label"].text, "canlı")


class BudgetSummaryComputationTest(AccountFixtureMixin, unittest.TestCase):
    """compute_budget_summary saf hesabı (widget'a dokunmaz)."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()
        from database.init_db import initialize_database
        initialize_database()
        self.account_id = self.create_test_account(balance=10000.0)
        from mixins.budget_mixin import BudgetMixin
        self.compute = BudgetMixin.compute_budget_summary

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def _plan_expense(self, amount, category="Süpermarket"):
        from database.db import get_connection
        conn = get_connection()
        conn.execute(
            """INSERT INTO monthly_budget_plan
               (type, name, amount, target_month, target_year, category_name,
                rollover_enabled, is_template, alert_threshold_pct)
               VALUES ('expense', ?, ?, 6, 2026, ?, 0, 0, 80)""",
            (category, amount, category),
        )
        conn.commit()
        conn.close()

    def _spend(self, amount, category="Süpermarket"):
        from services.transaction_service import TransactionService
        TransactionService.add_transaction(
            account_id=self.account_id, amount=amount,
            transaction_type="expense", category=category,
            description=category, transaction_date="2026-06-15 12:00:00",
            enforce_credit_limit=False, detect_subscription=False,
        )

    def test_zero_without_a_plan(self):
        self.assertEqual(self.compute(6, 2026), (0.0, 0.0, 0.0))

    def test_spent_against_limit(self):
        self._plan_expense(2000.0)
        self._spend(500.0)
        spent, limit, percent = self.compute(6, 2026)
        self.assertAlmostEqual(spent, 500.0, places=2)
        self.assertAlmostEqual(limit, 2000.0, places=2)
        self.assertAlmostEqual(percent, 25.0, places=1)

    def test_overspend_reports_real_percent_not_clamped(self):
        """Aşımı gizlemek yanıltıcı: %500 harcayan %100 görmemeli."""
        self._plan_expense(100.0)
        self._spend(500.0)
        _, _, percent = self.compute(6, 2026)
        self.assertAlmostEqual(percent, 500.0, places=1)


class ShowBudgetPlannerTest(unittest.TestCase):
    """show_budget_planner panel diyaloğunu kurup dolduruyor mu?

    MDDialog/Factory gerçek pencere ister; dış bağımlılıklar mock'lanıp yalnız
    metodun KENDİ akışı (panel referansı + doldurma çağrıları) doğrulanır.
    """

    def test_creates_panel_and_populates_it(self):
        from mixins.budget_mixin import BudgetMixin

        class _App(BudgetMixin):
            pass

        app = _App()
        app.active_budget_month = 6
        app.active_budget_year = 2026

        panel = _panel_stub()
        calls = []
        app.setup_dynamic_months = lambda: calls.append("months")
        app.change_budget_month = lambda m, y=None: calls.append(("month", m, y))

        fake_dialog = SimpleNamespace(
            open=lambda: calls.append("open"),
            dismiss=lambda: None,
            bind=lambda **k: None,
        )

        # Factory dinamik __getattr__ kullandığından mock.patch.object çalışmaz;
        # gerçek bir sahte sınıf kaydedip panel örneğini ondan döndürüyoruz.
        from kivy.factory import Factory

        class _FakePanelCls:
            def __new__(cls, *a, **k):
                return panel

        Factory.register("BudgetPlannerPanel", cls=_FakePanelCls)
        try:
            with mock.patch("kivymd.uix.dialog.MDDialog",
                            return_value=fake_dialog), \
                 mock.patch("kivymd.uix.button.MDFlatButton",
                            return_value=SimpleNamespace()):
                app.show_budget_planner()
        finally:
            Factory.unregister("BudgetPlannerPanel")

        # Panel canlı referansa kondu ve id'leri çözülebiliyor.
        self.assertIs(app._budget_planner_panel, panel)
        self.assertIn("month_selector_container", app._planner_ids())
        # Detay listesi load_budget_list'e bağlandı.
        self.assertIs(
            app.bp_list_container, panel.ids["budget_detailed_list"])
        # Panel açıldıktan SONRA dolduruldu (boş ay seçiciyle açılmasın).
        self.assertIn("months", calls)
        self.assertTrue(
            any(isinstance(c, tuple) and c[0] == "month" for c in calls))
        self.assertIn("open", calls)


if __name__ == "__main__":
    unittest.main()
