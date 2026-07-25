"""Bütçe planlayıcının yeni hiyerarşisi ve ana sayfa veri köprüsü.

Planlayıcı `ui/dashboard.kv`'nin ortasından çıkarılıp `ui/tools.kv` içinde
`<BudgetPlannerPanel@MDCard>` olarak tanımlandı. Dinamik sınıf kuralı içindeki
id'ler PANELİN KENDİ `ids` sözlüğünde yaşar, `root.ids`'te DEĞİL — bu paket o
sözleşmeyi ve özet kartına giden veri köprüsünü kilitler.

Kivy widget ağacı kurulmaz; `ids` sözlükleri stub'lanır (tests/test_reset_flow
ve test_pending_panel'deki desen).
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


def _make_app(with_panel=True, with_summary=True):
    from mixins.budget_mixin import BudgetMixin

    class _App(BudgetMixin):
        pass

    app = _App()
    root_ids = _Ids()
    if with_panel:
        root_ids["budget_planner_panel"] = SimpleNamespace(ids=_Ids(
            month_selector_container=SimpleNamespace(
                children=[], clear_widgets=lambda: None,
                add_widget=lambda w: None),
            projection_label=SimpleNamespace(text=""),
            projection_icon=SimpleNamespace(icon="", text_color=None),
        ))
    if with_summary:
        root_ids["budget_summary_card"] = SimpleNamespace(ids=_Ids(
            budget_summary_text=SimpleNamespace(text=""),
            budget_summary_bar=SimpleNamespace(value=0),
        ))
    app.root = SimpleNamespace(ids=root_ids)
    return app


class PlannerIdResolutionTest(unittest.TestCase):
    """Panel taşındıktan sonra id çözümlemesi."""

    def test_ids_resolved_through_panel(self):
        app = _make_app()
        ids = app._planner_ids()
        self.assertIn("projection_label", ids)
        self.assertIn("month_selector_container", ids)

    def test_falls_back_to_root_ids_when_panel_absent(self):
        """Paneli KV'de geri taşıyan biri için güvenli davranış."""
        app = _make_app(with_panel=False)
        app.root.ids["projection_label"] = SimpleNamespace(text="")
        ids = app._planner_ids()
        self.assertIn("projection_label", ids)

    def test_no_root_yields_empty_mapping(self):
        app = _make_app()
        app.root = None
        self.assertEqual(app._planner_ids(), {})

    def test_summary_ids_resolved_through_card(self):
        app = _make_app()
        ids = app._summary_ids()
        self.assertIn("budget_summary_text", ids)
        self.assertIn("budget_summary_bar", ids)

    def test_summary_ids_empty_without_card(self):
        app = _make_app(with_summary=False)
        self.assertEqual(app._summary_ids(), {})


class BudgetSummaryBridgeTest(AccountFixtureMixin, unittest.TestCase):
    """Araçlar'daki planlayıcıdan ana sayfa kartına veri akışı."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()
        from database.init_db import initialize_database
        initialize_database()
        self.account_id = self.create_test_account(balance=10000.0)
        self.app = _make_app()
        self.app.active_budget_month = 6
        self.app.active_budget_year = 2026

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

    def test_summary_is_zero_without_a_plan(self):
        spent, limit, percent = self.app.compute_budget_summary(6, 2026)
        self.assertEqual((spent, limit, percent), (0.0, 0.0, 0.0))

    def test_summary_reports_spent_against_limit(self):
        self._plan_expense(2000.0)
        self._spend(500.0)

        spent, limit, percent = self.app.compute_budget_summary(6, 2026)
        self.assertAlmostEqual(spent, 500.0, places=2)
        self.assertAlmostEqual(limit, 2000.0, places=2)
        self.assertAlmostEqual(percent, 25.0, places=1)

    def test_overspend_reports_real_percent_not_clamped(self):
        """Aşımı gizlemek yanıltıcı olur: %500 harcayan %100 görmemeli.

        Sıkıştırma yalnız progress bar'da (0-100) uygulanır.
        """
        self._plan_expense(100.0)
        self._spend(500.0)
        _, _, percent = self.app.compute_budget_summary(6, 2026)
        self.assertAlmostEqual(percent, 500.0, places=1)

    def test_progress_bar_is_clamped_even_when_overspent(self):
        self._plan_expense(100.0)
        self._spend(500.0)
        self.app.refresh_budget_summary()

        ids = self.app._summary_ids()
        self.assertEqual(ids["budget_summary_bar"].value, 100.0)
        self.assertIn("500", ids["budget_summary_text"].text)

    def test_refresh_writes_into_summary_card(self):
        """Köprünün asıl işi: hesaplanan veri karta yazılmalı."""
        self._plan_expense(2000.0)
        self._spend(500.0)

        self.app.refresh_budget_summary()

        ids = self.app._summary_ids()
        self.assertAlmostEqual(ids["budget_summary_bar"].value, 25.0, places=1)
        text = ids["budget_summary_text"].text
        self.assertIn("500", text)
        self.assertIn("2.000", text)

    def test_refresh_reports_missing_plan(self):
        self.app.refresh_budget_summary()
        text = self.app._summary_ids()["budget_summary_text"].text
        self.assertIn("plan", text.lower())

    def test_refresh_is_safe_without_summary_card(self):
        """Kart yoksa (KV değişti/test ortamı) sessizce çıkmalı."""
        app = _make_app(with_summary=False)
        app.active_budget_month, app.active_budget_year = 6, 2026
        app.refresh_budget_summary()  # hata fırlatmamalı


if __name__ == "__main__":
    unittest.main()
