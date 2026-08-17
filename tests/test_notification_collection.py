"""Zilin ne göstereceğini toplayan mantık.

Zil bir tur boyunca hiçbir işleyicisi olmayan bir düğmeydi — dokununca dalga
animasyonu oynayıp hiçbir şey yapmıyordu. Bu paket, arkasındaki mantığın
gerçekten bir şey ürettiğini ve "7 gün içinde" kuralını ana sayfadaki
"Yaklaşan Ödemeler" kartıyla AYNI şekilde uyguladığını sabitler.

`collect_notifications` UI'dan bağımsız yazıldı ve `today` enjekte edilebiliyor;
aksi hâlde testler çalıştıkları güne göre sonuç değiştirirdi.
"""
import datetime
import os
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("ARCHLENCE_HEADLESS", "1")


# İMPORT MODÜL DÜZEYİNDE DEĞİL — `notification_mixin` KivyMD'yi çekiyor ve
# KivyMD import anında `dp(400)` çağırıyor. Pencere/metrik henüz kurulmamışken
# bu `TypeError: must be real number, not NoneType` veriyor ve test
# DISCOVERY'si sırasında koştuğu için TÜM paketi düşürüyor (ölçüldü: 150 hata).
# Depodaki diğer KivyMD'ye dokunan testler de aynı sebeple import'u metot
# içinde yapıyor.
def _module():
    from mixins import notification_mixin
    return notification_mixin


TODAY = datetime.date(2026, 8, 17)


def _due(offset):
    return (TODAY + datetime.timedelta(days=offset)).isoformat()


class CollectNotificationsTest(unittest.TestCase):

    def _run(self, pending=(), recurring=()):
        with mock.patch(
            "services.transaction_service.TransactionService"
            ".get_pending_transactions",
            return_value=list(pending),
        ), mock.patch(
            "database.db.get_active_recurring_payments",
            return_value=list(recurring),
        ):
            return _module().collect_notifications(today=TODAY)

    def test_no_data_gives_no_rows(self):
        self.assertEqual(self._run(), [])

    def test_pending_transaction_becomes_a_row(self):
        rows = self._run(pending=[
            {"description": "Kira", "execution_date": _due(3)},
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Kira")
        self.assertEqual(rows[0]["kind"], "pending")

    def test_payment_inside_the_window_is_included(self):
        rows = self._run(recurring=[
            {"name": "Netflix",
             "next_due_date": _due(_module().UPCOMING_WINDOW_DAYS)},
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "recurring")

    def test_payment_beyond_the_window_is_excluded(self):
        """Eşik ana sayfadaki kartla AYNI olmalı; iki farklı gerçek olmaz."""
        rows = self._run(recurring=[
            {"name": "Uzak",
             "next_due_date": _due(_module().UPCOMING_WINDOW_DAYS + 1)},
        ])
        self.assertEqual(rows, [])

    def test_overdue_payment_is_included_and_labelled(self):
        rows = self._run(recurring=[
            {"name": "Gecikmiş", "next_due_date": _due(-3)},
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["subtitle"], "Gecikti")

    def test_due_today_is_labelled_separately(self):
        rows = self._run(recurring=[
            {"name": "Bugünkü", "next_due_date": _due(0)},
        ])
        self.assertEqual(rows[0]["subtitle"], "Bugün")

    def test_rows_are_ordered_oldest_first(self):
        """Gecikmiş olan en üstte görünmeli."""
        rows = self._run(recurring=[
            {"name": "Sonra", "next_due_date": _due(5)},
            {"name": "Gecikmiş", "next_due_date": _due(-2)},
        ])
        self.assertEqual([r["title"] for r in rows], ["Gecikmiş", "Sonra"])

    def test_both_sources_appear_together(self):
        rows = self._run(
            pending=[{"description": "Bekleyen", "execution_date": _due(1)}],
            recurring=[{"name": "Ödeme", "next_due_date": _due(2)}],
        )
        self.assertEqual({r["kind"] for r in rows}, {"pending", "recurring"})

    def test_malformed_due_date_is_skipped_not_fatal(self):
        """Bozuk tek tarih tüm zili düşürmemeli."""
        rows = self._run(recurring=[
            {"name": "Bozuk", "next_due_date": "17/08/2026"},
            {"name": "Saglam", "next_due_date": _due(1)},
        ])
        self.assertEqual([r["title"] for r in rows], ["Saglam"])

    def test_missing_due_date_is_skipped(self):
        rows = self._run(recurring=[{"name": "Tarihsiz", "next_due_date": None}])
        self.assertEqual(rows, [])

    def test_nameless_records_still_render_something(self):
        rows = self._run(
            pending=[{"description": None, "execution_date": _due(1)}],
        )
        self.assertTrue(rows[0]["title"])


if __name__ == "__main__":
    unittest.main()
