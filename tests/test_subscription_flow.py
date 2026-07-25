"""Abonelik yönetimi akışının testleri (Görev #5).

Kapsam — spec 3.2 ve 5.2:
  * "Sadece bu ay için sil": abonelik aktif kalır, yalnız bir dönem atlanır.
  * "Bu aydan ve sonraki tüm aylardan sil": kalıcı iptal.
  * İade sorusu: bu ay kesilen ücret bakiyeye geri eklenebilir.
  * Zam senaryosu: abonelik silinip yeniden kurulmadan ücreti düzenlenebilir.
  * Marka logosu (brand icon) aboneliğin adından çözülebilir.

Aboneliklerin tek kayıt yeri `recurring_payments`; `subscriptions` tablosu
hiçbir yerden okunmadığı için kasıtlı olarak kullanılmaz.
"""
import os
import tempfile
import unittest
from datetime import date
from unittest import mock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fixtures import AccountFixtureMixin


class SubscriptionFlowTest(AccountFixtureMixin, unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()

        from database.init_db import initialize_database
        initialize_database()

        from database.db import DEFAULT_ACCOUNT_ID
        self.account_id = self.create_test_account(
            name="Abonelik Testi Vadesiz", balance=5000.0)
        self.assertEqual(
            self.account_id, DEFAULT_ACCOUNT_ID,
            "insert_recurring_payment varsayılan hesabı kullanıyor.",
        )

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    # ─── Yardımcılar ─────────────────────────────────────────────────────────

    def _add_subscription(self, name="Netflix", amount=149.99,
                          frequency="monthly", due=None, day=15):
        from database.db import (
            get_active_recurring_payments, insert_recurring_payment,
        )
        insert_recurring_payment(
            name, amount, "Dijital Platformlar", frequency,
            due or date.today().isoformat(), auto_deduct=0, recurrence_day=day,
        )
        return next(
            p for p in get_active_recurring_payments() if p["name"] == name
        )

    def _balance(self):
        from services.account_service import AccountService
        return AccountService.get_account(self.account_id)["balance"]

    def _active_names(self):
        from database.db import get_active_recurring_payments
        return {p["name"] for p in get_active_recurring_payments()}

    # ─── Kalıcı iptal ────────────────────────────────────────────────────────

    def test_cancel_deactivates_without_deleting_row(self):
        """Kalıcı iptal: aktif listeden çıkar ama satır korunur.

        Fiziksel silme, geçmiş işlemleri abonelik radarının yeniden
        'keşfedeceği' bir adaya dönüştürürdü.
        """
        from services.recurring_service import cancel_subscription
        payment = self._add_subscription()

        self.assertTrue(cancel_subscription(payment["id"]))
        self.assertNotIn("Netflix", self._active_names())

        from database.db import get_connection
        conn = get_connection()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM recurring_payments").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(total, 1, "Satır silinmemeli, yalnız is_active=0 olmalı")

    def test_cancel_is_reported_false_for_unknown_id(self):
        from services.recurring_service import cancel_subscription
        self.assertFalse(cancel_subscription(9999))

    # ─── Sadece bu ay (bir dönem atla) ───────────────────────────────────────

    def test_skip_advances_due_date_and_keeps_subscription_active(self):
        """'Sadece bu ay için sil': gelecek aylar kaybedilmez."""
        from services.recurring_service import skip_next_occurrence
        payment = self._add_subscription(due="2026-03-15", day=15)

        new_due = skip_next_occurrence(payment["id"])

        self.assertEqual(new_due, "2026-04-15")
        self.assertIn("Netflix", self._active_names(),
                      "Bir dönem atlamak aboneliği iptal etmemeli")

    def test_skip_respects_short_months(self):
        """31'inde tahsil edilen abonelik, 30 günlük ayda taşmamalı."""
        from services.recurring_service import skip_next_occurrence
        payment = self._add_subscription(due="2026-03-31", day=31)
        self.assertEqual(skip_next_occurrence(payment["id"]), "2026-04-30")

    def test_skip_returns_none_for_cancelled_subscription(self):
        from services.recurring_service import (
            cancel_subscription, skip_next_occurrence,
        )
        payment = self._add_subscription()
        cancel_subscription(payment["id"])
        self.assertIsNone(skip_next_occurrence(payment["id"]))

    # ─── Zam / fiyat düzenleme (spec 5.2) ────────────────────────────────────

    def test_amount_can_be_edited_without_recreating(self):
        from database.db import get_active_recurring_payments
        from services.recurring_service import update_subscription_amount
        payment = self._add_subscription(amount=149.99, due="2026-03-15")

        self.assertTrue(update_subscription_amount(payment["id"], 229.99))

        updated = next(
            p for p in get_active_recurring_payments() if p["name"] == "Netflix"
        )
        self.assertAlmostEqual(updated["amount"], 229.99, places=2)
        self.assertEqual(
            updated["next_due_date"], "2026-03-15",
            "Zam vadeyi kaydırmamalı",
        )

    def test_amount_edit_rejects_non_positive(self):
        from services.recurring_service import update_subscription_amount
        payment = self._add_subscription()
        with self.assertRaises(ValueError):
            update_subscription_amount(payment["id"], 0)

    # ─── İade (spec 3.2) ─────────────────────────────────────────────────────

    def test_refund_returns_this_months_charge_to_balance(self):
        from database.db import process_due_recurring_payment
        from services.recurring_service import refund_current_period_charge
        payment = self._add_subscription(amount=100.0)

        before = self._balance()
        process_due_recurring_payment(payment)
        self.assertAlmostEqual(self._balance(), before - 100.0, places=2)

        refunded = refund_current_period_charge(payment["id"])

        self.assertAlmostEqual(refunded, 100.0, places=2)
        self.assertAlmostEqual(self._balance(), before, places=2)

    def test_refund_is_zero_when_nothing_charged_this_month(self):
        from services.recurring_service import refund_current_period_charge
        payment = self._add_subscription()
        before = self._balance()

        self.assertEqual(refund_current_period_charge(payment["id"]), 0.0)
        self.assertAlmostEqual(self._balance(), before, places=2)

    def test_refund_reverses_instead_of_deleting_history(self):
        """Orijinal gider korunur, dengeleyici gelir yazılır (çift kayıt)."""
        from database.db import get_connection, process_due_recurring_payment
        from services.recurring_service import refund_current_period_charge
        payment = self._add_subscription(amount=100.0)
        process_due_recurring_payment(payment)
        refund_current_period_charge(payment["id"])

        conn = get_connection()
        try:
            expenses = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE type = 'expense'"
            ).fetchone()[0]
            incomes = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE type = 'income'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual((expenses, incomes), (1, 1))

    def test_refund_writes_ledger_event(self):
        from database.db import get_connection, process_due_recurring_payment
        from services.recurring_service import refund_current_period_charge
        payment = self._add_subscription(amount=100.0)
        process_due_recurring_payment(payment)
        refund_current_period_charge(payment["id"])

        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT delta FROM balance_events WHERE source = ?",
                ("subscription_refund",),
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["delta"], 100.0, places=2)

    def test_find_charge_ignores_other_subscriptions(self):
        """Aynı kategorideki başka bir aboneliğin tahsilatı karışmamalı."""
        from database.db import process_due_recurring_payment
        from services.recurring_service import find_current_period_charge
        netflix = self._add_subscription(name="Netflix", amount=100.0)
        spotify = self._add_subscription(name="Spotify", amount=60.0)

        process_due_recurring_payment(spotify)

        self.assertIsNone(find_current_period_charge(netflix["id"]))
        found = find_current_period_charge(spotify["id"])
        self.assertIsNotNone(found)
        self.assertAlmostEqual(found["amount"], 60.0, places=2)

    # ─── Marka logosu ────────────────────────────────────────────────────────

    def test_subscription_name_resolves_to_brand_icon(self):
        """Abonelik adı, kart üzerinde gösterilecek logoya çözülebilmeli."""
        from services.brand_icon_service import classify_brand
        for name in ("Netflix", "netflix.com 12/2026", "Spotify Premium",
                     "Disney+"):
            with self.subTest(name=name):
                self.assertIsNotNone(classify_brand(name)[0])

    def test_unknown_brand_has_no_icon(self):
        from services.brand_icon_service import classify_brand
        self.assertIsNone(classify_brand("Mahalle bakkalı")[0])


if __name__ == "__main__":
    unittest.main()
