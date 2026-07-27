"""Hesap listesi (RAM snapshot) ↔ gerçek DB bakiyeleri senkronizasyonu.

HATA: Kullanıcı yeni bir hesap eklediğinde ana sayfadaki toplam güncelleniyor
ama "Kartlarım" listesi eski hâlinde kalıyordu — yeni hesap hiç görünmüyor ya
da bakiyesi eski değerle çiziliyordu.

KÖK NEDEN sayıların hesaplanışı değil, OKUMA YOLLARININ ayrışmasıydı:

  * Ana sayfa toplamı (`_compute_dashboard_metrics`) her çağrıda DB'den taze
    okur → yeni hesabı hemen görür.
  * `render_accounts` hız için hiç SQL çalıştırmaz, yalnızca
    `asset_service._asset_data_cache` snapshot'ından çizer → yazımdan sonra
    biri snapshot'ı tazelemezse ESKİ veriyi çizer.

Tazeleme her yazan akışa elle bırakılmıştı ve çoğu unutmuştu: yalnızca işlem
ekleme ile kart silme doğru davranıyordu; hesap ekleme, kart borcu ödeme ve
birikim aktarımı unutulmuştu.

DÜZELTME: yazan taraf `mark_account_cache_stale()` ile bayrağı düşürür (tek
noktadan — `record_balance_event`, defter değişmezi sayesinde bakiyeye dokunan
her yol oradan geçer), okuyan taraf `ensure_account_cache_fresh()` ile gerekirse
tazeler. Bu testler bayrağın gerçekten düştüğünü ve okumanın taze veri
döndürdüğünü doğrular.
"""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")


class AccountCacheSyncTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()
        from database.init_db import initialize_database
        initialize_database()

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def _warm_cache(self):
        """Uygulama açılışındaki ısınmış snapshot'ı taklit eder."""
        import services.asset_service as asset_service
        asset_service.refresh_account_cache_snapshot()
        self.assertFalse(asset_service._account_cache_stale)
        return asset_service

    def _cached_names(self, asset_service):
        cache = asset_service.ensure_account_cache_fresh()
        return {a["name"] for a in (cache.get("accounts") or [])}

    def test_new_account_appears_in_cached_list(self):
        """Asıl hata: eklenen hesap listede hiç görünmüyordu."""
        from services.account_service import AccountService

        asset_service = self._warm_cache()
        self.assertNotIn("Yeni Hesap", self._cached_names(asset_service))

        AccountService.create_account("Yeni Hesap", "checking",
                                      initial_balance=5000)

        self.assertTrue(asset_service._account_cache_stale,
                        "hesap açılışı snapshot'ı bayat işaretlemeli")
        self.assertIn("Yeni Hesap", self._cached_names(asset_service))

    def test_cached_summary_matches_db_after_account_added(self):
        """Liste ile ana sayfa toplamı aynı sayıyı göstermeli."""
        from services.account_service import AccountService
        from services.queries import DashboardService

        asset_service = self._warm_cache()
        AccountService.create_account("Vadesiz", "checking",
                                      initial_balance=12500)

        cache = asset_service.ensure_account_cache_fresh()
        self.assertAlmostEqual(
            cache["summary"]["net"],
            DashboardService.get_total_balance(),
            places=2,
        )

    def test_transaction_updates_cached_balance(self):
        """İşlem sonrası listedeki bakiye de değişmeli (eskiden eski kalırdı)."""
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        account_id = AccountService.create_account("Vadesiz", "checking",
                                                   initial_balance=1000)
        asset_service = self._warm_cache()

        TransactionService.add_transaction(
            account_id=account_id, amount=250, transaction_type="expense",
            category="Market", description="test",
        )

        self.assertTrue(asset_service._account_cache_stale)
        cache = asset_service.ensure_account_cache_fresh()
        balance = next(a["balance"] for a in cache["accounts"]
                       if a["id"] == account_id)
        self.assertAlmostEqual(balance, 750.0, places=2)

    def test_card_payment_updates_both_cached_accounts(self):
        """Kart borcu ödemesi iki hesabı da etkiler; ikisi de tazelenmeli."""
        from services.account_service import AccountService

        checking_id = AccountService.create_account("Vadesiz", "checking",
                                                    initial_balance=5000)
        card_id = AccountService.create_account("Kart", "credit_card",
                                                initial_balance=2000,
                                                credit_limit=10000)
        asset_service = self._warm_cache()

        AccountService.pay_credit_card_debt(card_id, checking_id, 500)

        self.assertTrue(asset_service._account_cache_stale)
        cache = asset_service.ensure_account_cache_fresh()
        by_id = {a["id"]: a for a in cache["accounts"]}
        self.assertAlmostEqual(by_id[checking_id]["balance"], 4500.0, places=2)
        self.assertAlmostEqual(by_id[card_id]["debt"], 1500.0, places=2)

    def test_savings_deposit_updates_cached_balance(self):
        """Birikim aktarımı da bakiyeyi düşürür; liste bunu göstermeli."""
        from services.account_service import AccountService
        from services.savings_service import SavingsService

        account_id = AccountService.create_account("Vadesiz", "checking",
                                                   initial_balance=3000)
        goal_id = SavingsService.create_goal("Tatil", 10000)
        asset_service = self._warm_cache()

        SavingsService.deposit_to_goal(goal_id, 800, account_id)

        self.assertTrue(asset_service._account_cache_stale)
        cache = asset_service.ensure_account_cache_fresh()
        balance = next(a["balance"] for a in cache["accounts"]
                       if a["id"] == account_id)
        self.assertAlmostEqual(balance, 2200.0, places=2)

    def test_fresh_read_is_skipped_when_nothing_changed(self):
        """Bayrak düşmediyse tazeleme yapılmaz — Instant Render korunur."""
        asset_service = self._warm_cache()

        with mock.patch.object(
            asset_service, "refresh_account_cache_snapshot"
        ) as refresh:
            asset_service.ensure_account_cache_fresh()
            refresh.assert_not_called()

    def test_unwarmed_cache_is_left_to_the_warmup_worker(self):
        """ready=False iken araya girilmez; açılış worker'ı zaten taze okuyacak.

        Araya girilseydi ağ gerektiren `active_assets_result` alanı None'a
        düşerdi (Varlıklarım kartı boş çizilirdi).
        """
        import services.asset_service as asset_service

        asset_service._asset_data_cache = {
            "summary": {}, "accounts": [], "recent": {},
            "active_assets_result": None, "ready": False,
        }
        asset_service.mark_account_cache_stale()

        with mock.patch.object(
            asset_service, "refresh_account_cache_snapshot"
        ) as refresh:
            asset_service.ensure_account_cache_fresh()
            refresh.assert_not_called()
        self.assertTrue(asset_service._account_cache_stale,
                        "bayrak düşmemeli — tazeleme hâlâ borçlu")


if __name__ == "__main__":
    unittest.main()
