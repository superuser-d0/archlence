"""Dashboard metrik önbelleği — kazanç değil, DOĞRU GEÇERSİZ KILMA testi.

NEDEN ÖNBELLEK: `_compute_dashboard_metrics` maliyetinin ~%99'u AES-GCM şifre
çözme. Tutarlar şifreli TEXT olduğu için SQL'de toplanamıyor; her satır
Python'da çözülmek zorunda. 10.000 işlemli bir profilde tek çağrı 10.800
`decrypt` ve ~328 ms. Çözmeyi hızlandırmak mümkün değil (maliyet PyCryptodome'un
kayıt başına üç cipher nesnesi kurmasında), o yüzden tek gerçek kazanç
GEREKMEDİKÇE HİÇ HESAPLAMAMAK: ölçüldü, önbellekli çağrı 0 decrypt / ~0 ms.

Bu dosyanın asıl işi hızı kutlamak değil, önbelleğin BAYAT VERİ
göstermediğini sabitlemek — yanlış bir bakiye, yavaş bir bakiyeden çok daha
kötüdür.
"""
import datetime
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("ARCHLENCE_HEADLESS", "1")


class _App:
    """`_compute_dashboard_metrics` için asgari sahte `self`."""

    home_filter = "Bugün"

class DashboardMetricsCacheTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()
        from database.init_db import initialize_database
        initialize_database()

        from services.account_service import AccountService
        self.account_id = AccountService.create_account(
            name="Nakit", account_type="checking", initial_balance=0.0)
        self.app = _App()

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def _metrics(self):
        import main as main_mod
        return main_mod.ArchlenceApp._compute_dashboard_metrics(self.app)

    def _decrypt_calls(self, fn):
        """`fn` sırasında kaç kayıt çözüldüğünü sayar."""
        import services.financial_summary_service as fss

        real = fss.decrypt
        count = {"n": 0}

        def counting(*args, **kwargs):
            count["n"] += 1
            return real(*args, **kwargs)

        with mock.patch.object(fss, "decrypt", counting):
            result = fn()
        return count["n"], result

    def _add_expense(self, amount, category="Market"):
        from services.transaction_service import TransactionService
        TransactionService.add_transaction(
            self.account_id, amount, "expense", category, "test")

    # ── Önbellek gerçekten çalışıyor mu ─────────────────────────────────

    def test_second_call_decrypts_nothing(self):
        self._add_expense(100.0)
        first, _ = self._decrypt_calls(self._metrics)
        second, _ = self._decrypt_calls(self._metrics)

        self.assertGreater(first, 0, "ilk çağrı gerçekten hesaplamalı")
        self.assertEqual(second, 0, "ikinci çağrı hiç çözmemeli")

    # ── Bayat veri göstermemeli — asıl risk bu ──────────────────────────

    def test_a_new_transaction_invalidates_the_cache(self):
        self._add_expense(100.0)
        before = self._metrics()["total_expense"]

        self._add_expense(50.0)
        after = self._metrics()["total_expense"]

        self.assertNotEqual(
            before, after,
            "yeni işlemden sonra önbellek bayat kalmamalı",
        )

    def test_changing_category_importance_invalidates_the_cache(self):
        """Bakiyeyi HİÇ değiştirmeyen ama özeti değiştiren durum.

        `importance`, `summarize_transactions`'ın main/extra kovalarını
        belirliyor. `record_balance_event` bu yolda ÇALIŞMADIĞI için sürüm
        kendiliğinden artmıyordu — `mark_financial_data_changed()` tam bunun
        için eklendi. O çağrı olmadan bu test bayat veri görürdü.
        """
        from services import asset_service

        self._add_expense(100.0, category="Market")
        self._metrics()  # önbelleği doldur
        revision_before = asset_service.get_financial_data_revision()

        asset_service.mark_financial_data_changed()
        self.assertGreater(
            asset_service.get_financial_data_revision(), revision_before,
            "sürüm artmazsa önbellek asla tazelenmez",
        )
        calls, _ = self._decrypt_calls(self._metrics)
        self.assertGreater(calls, 0, "sürüm artınca yeniden hesaplanmalı")

    def test_changing_the_period_filter_invalidates_the_cache(self):
        self._add_expense(100.0)
        self._metrics()

        self.app.home_filter = "1 Ay"
        calls, _ = self._decrypt_calls(self._metrics)
        self.assertGreater(
            calls, 0, "farklı dönem farklı sonuç verir, yeniden hesaplanmalı")

    def test_a_new_day_invalidates_the_cache(self):
        """Veri değişmese bile gün dönünce 'Bugün' penceresi kayar."""
        self._add_expense(100.0)
        self._metrics()

        real_date = datetime.date
        tomorrow = real_date.today() + datetime.timedelta(days=1)

        class _Tomorrow(real_date):
            @classmethod
            def today(cls):
                return tomorrow

        with mock.patch.object(datetime, "date", _Tomorrow):
            calls, _ = self._decrypt_calls(self._metrics)
        self.assertGreater(calls, 0, "gün dönünce yeniden hesaplanmalı")

    def test_cached_value_matches_a_freshly_computed_one(self):
        """Önbellek doğru sonucu saklamalı — hızlı ama yanlış olmamalı."""
        self._add_expense(120.0)
        self._add_expense(80.0)

        cached = self._metrics()
        self.app._dashboard_metrics_cache = None  # zorla yeniden hesapla
        fresh = self._metrics()

        for key in ("total_income", "total_expense", "total_balance",
                    "period_income", "period_expense", "period_net"):
            self.assertEqual(cached[key], fresh[key], f"{key} uyuşmuyor")

    def test_dashboard_total_matches_accounts_after_savings_transfer(self):
        from services.queries import DashboardService
        from services.savings_service import SavingsService

        goal_id = SavingsService.create_goal("Emergency", 1000)
        SavingsService.deposit_to_goal(goal_id, 250, self.account_id)
        metrics = self._metrics()

        self.assertEqual(
            metrics["total_balance"],
            DashboardService.get_total_balance(),
        )


if __name__ == "__main__":
    unittest.main()
