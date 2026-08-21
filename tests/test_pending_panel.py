"""Bekleyen İşlemler paneli / UI mixin testleri (Görev #4).

Servis katmanı tests/test_pending_transactions.py'de kapsanıyor; burada UI
mixin'inin sözleşmesi test ediliyor: özet kartı doğru zamanlarda görünüyor mu,
satır etiketleri doğru mu, iptal/erteleme eylemleri servisi çağırıp yüzeyleri
tazeliyor mu.

Kivy widget ağacı kurmadan çalışır: `root.ids` sözlük benzeri bir stub ile
taklit edilir (tests/test_reset_flow.py'deki _Ids deseni), böylece test
headless kalır ve pencere sağlayıcısı gerektirmez.
"""
import os
import tempfile
import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest import mock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fixtures import AccountFixtureMixin


class _Ids(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class _Card(SimpleNamespace):
    """Kartın height/opacity/disabled durumunu izleyen basit stub."""


def _make_app():
    """PendingMixin'i pencere kurmadan tek başına örnekler."""
    from mixins.pending_mixin import PendingMixin

    class _App(PendingMixin):
        def __init__(self):
            self.root = SimpleNamespace(ids=_Ids(
                pending_tx_card=_Card(height=0, opacity=0, disabled=True),
                pending_tx_summary=SimpleNamespace(text=""),
            ))
            self.refreshed = []


        def safe_refresh_charts(self):
            self.refreshed.append("charts")

        def load_recent_transactions(self):
            self.refreshed.append("recent")

    return _App()


class PendingSummaryCardTest(AccountFixtureMixin, unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()
        from database.init_db import initialize_database
        initialize_database()
        self.account_id = self.create_test_account(balance=1000.0)
        self.app = _make_app()

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def _add_pending(self, amount, tx_type, days_ahead, category="Maaş"):
        from services.transaction_service import TransactionService
        when = (date.today() + timedelta(days=days_ahead)).isoformat()
        TransactionService.add_transaction(
            account_id=self.account_id, amount=amount,
            transaction_type=tx_type, category=category,
            description=category, transaction_date=f"{when} 09:00:00",
            enforce_credit_limit=False,
        )

    def _pending(self):
        from services.transaction_service import TransactionService
        return TransactionService.get_pending_transactions()


    def test_card_stays_hidden_when_nothing_pending(self):
        """Boş 'hiç yok' kartı dashboard'da yer israfı olurdu."""
        self.app.render_pending_summary([])
        card = self.app.root.ids.pending_tx_card
        self.assertEqual(card.height, 0)
        self.assertEqual(card.opacity, 0)
        self.assertTrue(card.disabled)
        self.assertEqual(self.app.root.ids.pending_tx_summary.text, "")

    def test_card_appears_when_pending_exists(self):
        self._add_pending(40000.0, "income", 5)
        self.app.render_pending_summary(self._pending())

        card = self.app.root.ids.pending_tx_card
        self.assertGreater(card.height, 0)
        self.assertEqual(card.opacity, 1)
        self.assertFalse(card.disabled)

    def test_summary_splits_income_and_expense(self):
        self._add_pending(40000.0, "income", 3)
        self._add_pending(1500.0, "expense", 6, category="Elektrik")
        self.app.render_pending_summary(self._pending())

        text = self.app.root.ids.pending_tx_summary.text
        self.assertIn("2", text)
        self.assertIn("40.000,00", text)
        self.assertIn("1.500,00", text)

    def test_summary_reports_nearest_date(self):
        self._add_pending(100.0, "expense", 9, category="Kira")
        self._add_pending(200.0, "expense", 2, category="Su")
        self.app.render_pending_summary(self._pending())

        nearest = (date.today() + timedelta(days=2)).isoformat()
        self.assertIn(nearest, self.app.root.ids.pending_tx_summary.text)

    def test_card_hides_again_after_last_pending_cleared(self):
        self._add_pending(100.0, "income", 4)
        self.app.render_pending_summary(self._pending())
        self.assertGreater(self.app.root.ids.pending_tx_card.height, 0)

        from services.transaction_service import TransactionService
        TransactionService.cancel_pending_transaction(self._pending()[0]["id"])
        self.app.render_pending_summary(self._pending())
        self.assertEqual(self.app.root.ids.pending_tx_card.height, 0)


class PendingRowActionsTest(AccountFixtureMixin, unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()
        from database.init_db import initialize_database
        initialize_database()
        self.account_id = self.create_test_account(balance=1000.0)
        self.app = _make_app()

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def _add_pending(self, amount=500.0, tx_type="income", days_ahead=5):
        from services.transaction_service import TransactionService
        when = (date.today() + timedelta(days=days_ahead)).isoformat()
        TransactionService.add_transaction(
            account_id=self.account_id, amount=amount,
            transaction_type=tx_type, category="Maaş", description="Maaş",
            transaction_date=f"{when} 09:00:00", enforce_credit_limit=False,
        )
        return TransactionService.get_pending_transactions()[0]

    def _pending_count(self):
        from services.transaction_service import TransactionService
        return len(TransactionService.get_pending_transactions())

    def _balance(self):
        from services.account_service import AccountService
        return AccountService.get_account(self.account_id)["balance"]

    def test_cancel_removes_pending_and_refreshes_views(self):
        item = self._add_pending()
        with mock.patch("mixins.pending_mixin.Clock.schedule_once",
                        side_effect=lambda cb, *a: cb(0)), \
             mock.patch("mixins.pending_mixin.toast"), \
             mock.patch("mixins.pending_mixin.threading.Thread",
                        side_effect=lambda target, daemon=None: SimpleNamespace(
                            start=target)):
            self.app.cancel_pending_transaction(item)

        self.assertEqual(self._pending_count(), 0)
        self.assertIn("charts", self.app.refreshed)

    def test_cancel_does_not_touch_balance(self):
        """Bekleyen kayıt bakiyeye hiç girmemişti; iptal düzeltme yapmamalı."""
        item = self._add_pending()
        before = self._balance()
        with mock.patch("mixins.pending_mixin.Clock.schedule_once",
                        side_effect=lambda cb, *a: cb(0)), \
             mock.patch("mixins.pending_mixin.toast"), \
             mock.patch("mixins.pending_mixin.threading.Thread",
                        side_effect=lambda target, daemon=None: SimpleNamespace(
                            start=target)):
            self.app.cancel_pending_transaction(item)
        self.assertAlmostEqual(self._balance(), before, places=2)

    def test_reschedule_to_today_settles_immediately(self):
        """Tarihi bugüne çekmek 'değişmedi' hissi bırakmamalı: hemen işlenir."""
        item = self._add_pending(amount=750.0)
        before = self._balance()

        with mock.patch("mixins.pending_mixin.Clock.schedule_once",
                        side_effect=lambda cb, *a: cb(0)), \
             mock.patch("mixins.pending_mixin.toast"), \
             mock.patch("mixins.pending_mixin.threading.Thread",
                        side_effect=lambda target, daemon=None: SimpleNamespace(
                            start=target)):
            self.app._apply_pending_reschedule(item, date.today().isoformat())

        self.assertEqual(self._pending_count(), 0)
        self.assertAlmostEqual(self._balance(), before + 750.0, places=2)

    def test_reschedule_further_out_keeps_it_pending(self):
        item = self._add_pending()
        before = self._balance()
        far = (date.today() + timedelta(days=40)).isoformat()

        with mock.patch("mixins.pending_mixin.Clock.schedule_once",
                        side_effect=lambda cb, *a: cb(0)), \
             mock.patch("mixins.pending_mixin.toast"), \
             mock.patch("mixins.pending_mixin.threading.Thread",
                        side_effect=lambda target, daemon=None: SimpleNamespace(
                            start=target)):
            self.app._apply_pending_reschedule(item, far)

        from services.transaction_service import TransactionService
        remaining = TransactionService.get_pending_transactions()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["execution_date"], far)
        self.assertAlmostEqual(self._balance(), before, places=2)


class PendingRowLabelTest(unittest.TestCase):
    """Satır metni saf biçimlendirme; ne DB ne çalışan MDApp gerektirir."""

    def _row_text(self, item):
        from mixins.pending_mixin import pending_row_text
        return pending_row_text(item)

    def test_income_row_is_signed_positive(self):
        future = (date.today() + timedelta(days=5)).isoformat()
        text = self._row_text({
            "id": 1, "description": "Maaş", "amount": 40000.0,
            "type": "income", "execution_date": future,
        })
        self.assertIn("+", text)
        self.assertIn("Maaş", text)
        self.assertIn(future, text)

    def test_expense_row_is_signed_negative(self):
        future = (date.today() + timedelta(days=2)).isoformat()
        text = self._row_text({
            "id": 2, "description": "Elektrik", "amount": 1500.0,
            "type": "expense", "execution_date": future,
        })
        self.assertIn("-", text)

    def test_today_and_tomorrow_are_worded(self):
        today_text = self._row_text({
            "id": 3, "description": "Kira", "amount": 100.0,
            "type": "expense", "execution_date": date.today().isoformat(),
        })
        tomorrow_text = self._row_text({
            "id": 4, "description": "Su", "amount": 100.0,
            "type": "expense",
            "execution_date": (date.today() + timedelta(days=1)).isoformat(),
        })
        self.assertIn("today", today_text)
        self.assertIn("tomorrow", tomorrow_text)

    def test_unparseable_date_falls_back_to_raw_value(self):
        text = self._row_text({
            "id": 5, "description": "Bozuk", "amount": 10.0,
            "type": "expense", "execution_date": "",
        })
        self.assertIn("Bozuk", text)


if __name__ == "__main__":
    unittest.main()
