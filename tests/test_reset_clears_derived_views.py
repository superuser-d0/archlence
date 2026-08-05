"""Sıfırlama, TÜRETİLMİŞ görünümleri de temizlemeli.

HATA (kullanıcı bildirimi): "Ayarlar → Verileri Sil" sonrasında veritabanı
gerçekten boşalıyordu, ama ekranda iki bölüm silinmiş verinin sonucunu
göstermeye devam ediyordu:

  * "Algoritmik Öngörü" eski harcama yorumunu (ör. "%2798.6 arttı"),
  * "Varlık Geçmişi" eski satırlarını.

KÖK NEDEN: `delete_all_data` `refresh_dashboard_data()` çağırıyor ama o
fonksiyon bu ikisini KAPSAMIYOR. `generate_financial_advice()` ve
`load_asset_history()` yalnızca açılışta (`on_start`) ve kendi
tetikleyicilerinde (işlem ekleme / varlık satışı) çalışıyor — sıfırlama
yolunda hiç çağrılmıyorlardı.

Bu test gerçek pencere GEREKTİRMEZ: `delete_all_data`'yı asgari bir sahte
`self` ile çalıştırıp iki çağrının yapıldığını doğrular. Davranışın kendisi
ayrıca gerçek `ArchlenceApp` ile ölçüldü (öncesinde öngörü metni aynen
kalıyor ve varlık listesinde 1 satır duruyordu; sonrasında metin "veri yok"a
düşüyor ve satır sayısı 0 oluyor).
"""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("ARCHLENCE_HEADLESS", "1")


class _Ids(dict):
    """`"x" in root.ids` ve `root.ids.x` erişimlerinin ikisini de destekler."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class _Store:
    def __init__(self):
        self.cleared = False

    def clear(self):
        self.cleared = True

    def exists(self, key):
        return False

    def delete(self, key):
        pass


class ResetRefreshesDerivedViewsTest(unittest.TestCase):
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

    def _run_reset(self):
        """`delete_all_data`'yı asgari sahte `self` ile çalıştırır."""
        import main as main_mod

        class _Screen:
            current = "home"

        calls = []

        class _App:
            language = "tr"
            store = _Store()
            config_store = _Store()
            savings_goals = ["kalinti"]
            reset_input = type("_I", (), {"text": "SİL"})()

            def __init__(self):
                self.root = type("_R", (), {})()
                self.root.ids = _Ids(screen_manager=_Screen())

            def render_accounts(self):
                calls.append("render_accounts")

            def refresh_dashboard_data(self, *args, **kwargs):
                calls.append("refresh_dashboard_data")

            def generate_financial_advice(self, *args, **kwargs):
                calls.append("generate_financial_advice")

            def load_asset_history(self, *args, **kwargs):
                calls.append("load_asset_history")

        app = _App()
        with mock.patch.object(main_mod, "toast", lambda *a, **k: None), \
             mock.patch(
                 "services.asset_service.start_data_warmup",
                 lambda callback=None: None):
            main_mod.ArchlenceApp.delete_all_data(app)
        return calls

    def test_reset_regenerates_the_forecast(self):
        """Öngörü metni silinmiş harcamaların sonucunu göstermeye devam
        edemez — sıfırlamadan sonra yeniden hesaplanmalı."""
        self.assertIn("generate_financial_advice", self._run_reset())

    def test_reset_reloads_the_asset_history(self):
        """Varlık geçmişi listesi silinen satırları göstermeye devam edemez."""
        self.assertIn("load_asset_history", self._run_reset())

    def test_reset_still_does_what_it_already_did(self):
        """Var olan tazelemeler bozulmamalı."""
        calls = self._run_reset()
        self.assertIn("render_accounts", calls)
        self.assertIn("refresh_dashboard_data", calls)

    def test_reset_actually_empties_the_database(self):
        """Asıl sözleşme: ekran tazelense de veri gerçekten gitmeli."""
        from services.account_service import AccountService
        from database.db import managed_connection

        AccountService.create_account(
            name="Nakit", account_type="checking", initial_balance=500.0)
        self._run_reset()
        with managed_connection() as conn:
            remaining = conn.execute(
                "SELECT COUNT(*) FROM accounts").fetchone()[0]
        self.assertEqual(remaining, 0)


if __name__ == "__main__":
    unittest.main()
