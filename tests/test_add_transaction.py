"""İşlem ekleme diyaloğundaki tarih seçici ve status mantığı (Görev #3).

Kapsam:
  (a) Gelecek tarihli işlem `pending` kaydedilir, anlık bakiyeyi ETKİLEMEZ ve
      bekleyenler listesine düşer.
  (b) Geçmiş/bugün tarihli işlem `completed` kaydedilir ve bakiye HEMEN değişir.
  (c) Tarih butonunun etiketi ve gelecek-tarih ibaresinin görünürlüğü.
  (d) Yazılan `transaction_date` her zaman tam zaman damgası biçiminde —
      tarih-only bir satır ui/charts.py'nin zaman grafiğini kırıyordu.

UI tarafı Kivy widget ağacı kurmadan test edilir: TransactionMixin'in yalnız
tarih yardımcıları örneklenir (tests/test_pending_panel.py'deki stub deseni).
"""
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest import mock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fixtures import AccountFixtureMixin


class TransactionDateStatusTest(AccountFixtureMixin, unittest.TestCase):
    """Servis seviyesinde tarih -> status -> bakiye sözleşmesi."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()
        from database.init_db import initialize_database
        initialize_database()
        self.account_id = self.create_test_account(balance=10000.0)

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def _add_on(self, day_offset, amount=500.0, tx_type="expense"):
        """Diyaloğun ürettiği zaman damgası biçimiyle işlem ekler."""
        from services.transaction_service import TransactionService
        target = date.today() + timedelta(days=day_offset)
        stamp = (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if day_offset == 0 else f"{target.isoformat()} 09:00:00"
        )
        TransactionService.add_transaction(
            account_id=self.account_id, amount=amount,
            transaction_type=tx_type, category="Süpermarket",
            description="Süpermarket", transaction_date=stamp,
            enforce_credit_limit=False,
        )
        return target

    def _balance(self):
        from services.account_service import AccountService
        return AccountService.get_account(self.account_id)["balance"]

    def _statuses(self):
        from database.db import get_connection
        conn = get_connection()
        try:
            return [r["status"] for r in conn.execute(
                "SELECT status FROM transactions ORDER BY id")]
        finally:
            conn.close()

    # ─── (a) Gelecek tarih ───────────────────────────────────────────────────

    def test_future_transaction_is_pending_and_balance_untouched(self):
        before = self._balance()
        self._add_on(day_offset=3)

        self.assertEqual(self._statuses(), ["pending"])
        self.assertAlmostEqual(self._balance(), before, places=2)

    def test_future_transaction_appears_in_pending_panel_source(self):
        from services.transaction_service import TransactionService
        target = self._add_on(day_offset=7, amount=1250.0)

        pending = TransactionService.get_pending_transactions()
        self.assertEqual(len(pending), 1)
        self.assertAlmostEqual(pending[0]["amount"], 1250.0, places=2)
        self.assertEqual(pending[0]["execution_date"], target.isoformat())

    def test_future_transaction_excluded_from_period_metrics(self):
        from services.transaction_service import TransactionService
        self._add_on(day_offset=5, amount=999.0)
        rows = TransactionService.get_transactions_by_period("Hayat Boyu")
        self.assertEqual(rows, [])

    # ─── (b) Geçmiş / bugün ──────────────────────────────────────────────────

    def test_past_transaction_is_completed_and_deducted(self):
        before = self._balance()
        self._add_on(day_offset=-4, amount=750.0)

        self.assertEqual(self._statuses(), ["completed"])
        self.assertAlmostEqual(self._balance(), before - 750.0, places=2)

    def test_today_transaction_is_completed_and_deducted(self):
        before = self._balance()
        self._add_on(day_offset=0, amount=300.0)

        self.assertEqual(self._statuses(), ["completed"])
        self.assertAlmostEqual(self._balance(), before - 300.0, places=2)

    def test_past_transaction_does_not_enter_pending_panel(self):
        from services.transaction_service import TransactionService
        self._add_on(day_offset=-2)
        self.assertEqual(TransactionService.get_pending_transactions(), [])

    def test_past_income_increases_balance(self):
        before = self._balance()
        self._add_on(day_offset=-1, amount=2000.0, tx_type="income")
        self.assertAlmostEqual(self._balance(), before + 2000.0, places=2)

    # ─── (d) Zaman damgası biçimi ────────────────────────────────────────────

    def test_stored_dates_keep_full_timestamp_format(self):
        """Tarih-only satır ui/charts.py zaman kovalarını kırıyordu."""
        from database.db import get_connection
        self._add_on(day_offset=-3)
        self._add_on(day_offset=0)
        self._add_on(day_offset=6)

        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT transaction_date FROM transactions").fetchall()
        finally:
            conn.close()

        self.assertEqual(len(rows), 3)
        for row in rows:
            with self.subTest(value=row["transaction_date"]):
                datetime.strptime(row["transaction_date"], "%Y-%m-%d %H:%M:%S")


class TransactionDateWidgetTest(unittest.TestCase):
    """Tarih butonu etiketi ve gelecek-tarih ibaresinin davranışı."""

    def _make_app(self):
        from mixins.transaction_mixin import TransactionMixin

        class _App(TransactionMixin):
            def __init__(self):
                self.date_button = SimpleNamespace(text="")
                self.date_hint_label = SimpleNamespace(
                    text="", height=0, opacity=0)
                self.reflowed = 0

            def _reflow_dialog(self):
                self.reflowed += 1

        return _App()

    def test_label_says_today_for_current_date(self):
        app = self._make_app()
        app.selected_transaction_date = date.today()
        self.assertIn("Bugün", app._transaction_date_label())

    def test_label_shows_iso_date_for_other_days(self):
        app = self._make_app()
        target = date.today() + timedelta(days=9)
        app.selected_transaction_date = target
        self.assertIn(target.isoformat(), app._transaction_date_label())

    def test_hint_appears_only_for_future_dates(self):
        app = self._make_app()
        app.selected_transaction_date = date.today() + timedelta(days=2)
        app._refresh_transaction_date_ui()

        self.assertGreater(app.date_hint_label.height, 0)
        self.assertEqual(app.date_hint_label.opacity, 1)
        self.assertIn("bekleyen", app.date_hint_label.text.lower())

    def test_hint_hidden_for_today(self):
        app = self._make_app()
        app.selected_transaction_date = date.today()
        app._refresh_transaction_date_ui()

        self.assertEqual(app.date_hint_label.height, 0)
        self.assertEqual(app.date_hint_label.opacity, 0)
        self.assertEqual(app.date_hint_label.text, "")

    def test_hint_hidden_for_past(self):
        app = self._make_app()
        app.selected_transaction_date = date.today() - timedelta(days=5)
        app._refresh_transaction_date_ui()
        self.assertEqual(app.date_hint_label.opacity, 0)

    def test_switching_future_to_today_clears_hint(self):
        """Kullanıcı fikrini değiştirince uyarı takılı kalmamalı."""
        app = self._make_app()
        app.selected_transaction_date = date.today() + timedelta(days=3)
        app._refresh_transaction_date_ui()
        self.assertEqual(app.date_hint_label.opacity, 1)

        app.selected_transaction_date = date.today()
        app._refresh_transaction_date_ui()
        self.assertEqual(app.date_hint_label.opacity, 0)

    def test_refresh_updates_button_text_and_reflows(self):
        app = self._make_app()
        target = date.today() + timedelta(days=4)
        app.selected_transaction_date = target
        app._refresh_transaction_date_ui()

        self.assertIn(target.isoformat(), app.date_button.text)
        self.assertGreaterEqual(app.reflowed, 1)

    def test_picker_callback_stores_selection(self):
        """Takvimden dönen tarih state'e yazılıp UI tazelenmeli."""
        app = self._make_app()
        app.selected_transaction_date = date.today()
        chosen = date.today() + timedelta(days=11)
        captured = {}

        def fake_picker(initial, on_save, min_date=None):
            captured["initial"] = initial
            captured["min_date"] = min_date
            on_save(None, chosen, None)

        app._open_date_picker = fake_picker
        app.open_transaction_date_picker()

        self.assertEqual(captured["initial"], date.today())
        self.assertEqual(app.selected_transaction_date, chosen)
        self.assertIn(chosen.isoformat(), app.date_button.text)

    def test_past_dates_are_not_selectable(self):
        """Geçmişe dönük işlem ekleme kaldırıldı (v0.0.1).

        İki katman birlikte doğrulanır: seçiciye `min_date=bugün` veriliyor
        (kullanıcı geçmişi hiç göremez) VE geri dönen tarih yine de geçmişse
        bugüne çekiliyor (savunma katmanı). İleri tarihli işlem akışı
        bozulmamalı — o ayrı testle kapsanıyor.
        """
        app = self._make_app()
        app.selected_transaction_date = date.today()
        past = date.today() - timedelta(days=30)
        captured = {}

        def fake_picker(initial, on_save, min_date=None):
            captured["initial"] = initial
            captured["min_date"] = min_date
            on_save(None, past, None)   # seçici atlansa bile geçmiş gelmesin

        app._open_date_picker = fake_picker
        app.open_transaction_date_picker()

        self.assertEqual(
            captured["min_date"], date.today(),
            "Tarih seçicisi bugünden öncesini göstermemeli.",
        )
        self.assertEqual(
            app.selected_transaction_date, date.today(),
            "Geçmiş tarih geldiğinde bugüne çekilmeli.",
        )

    def test_stale_past_selection_is_clamped_when_reopening(self):
        """Önceden kalmış geçmiş bir seçim, seçici yeniden açılınca bugüne çekilir."""
        app = self._make_app()
        app.selected_transaction_date = date.today() - timedelta(days=5)
        captured = {}

        def fake_picker(initial, on_save, min_date=None):
            captured["initial"] = initial

        app._open_date_picker = fake_picker
        app.open_transaction_date_picker()

        self.assertEqual(captured["initial"], date.today())


class RecurringCurrentPeriodPromptTest(unittest.TestCase):
    """Tekrarlayan gelir ve gider ilk dönem kararını açıkça istemeli."""

    def _make_app(self, transaction_type):
        from mixins.transaction_mixin import TransactionMixin

        app = TransactionMixin.__new__(TransactionMixin)
        app.selected_category = "Dijital Abonelik"
        app.selected_type = transaction_type
        app.amount_input = SimpleNamespace()
        app.recurring_switch = SimpleNamespace(active=True)
        app.recurring_name_input = SimpleNamespace(text="Aylık Plan")
        app.selected_frequency = "monthly"
        app.auto_deduct_switch = SimpleNamespace(active=False)
        app.recurrence_day_input = SimpleNamespace(text="15")
        app._ask_include_current_period = mock.Mock()
        return app

    def test_income_and_expense_both_request_current_period_decision(self):
        import mixins.transaction_mixin as transaction_module

        for transaction_type in ("income", "expense"):
            with self.subTest(transaction_type=transaction_type):
                app = self._make_app(transaction_type)
                with mock.patch.object(
                    transaction_module, "read_amount", return_value=100.0,
                ):
                    app.save_transaction()
                app._ask_include_current_period.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
