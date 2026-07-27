"""Açılış/işlem-ekleme donmalarını gideren üç düzeltmenin testleri.

BAĞLAM: `generate_financial_advice()` (main.py) 3 SQL sorgusu + Python
decrypt döngüsü yapıyordu ama hiç thread'e sarılmamıştı; açılışta VE her
başarılı işlem eklemesinde (transaction_mixin.py) ana thread'de senkron
çalışıyordu. Ayrıca `decrypt()`'in SÜRECİN İLK çağrısı ~250ms'lik tek
seferlik bir PBKDF2 anahtar türetmesi ödüyordu (ölçüldü) — hangi thread
önce çağırırsa o thread bloklanıyordu, pratikte neredeyse hep ana thread.
`vacuum_database()` de aynı şekilde ana thread'de senkron çalışıyordu.

Bu paket üçünün de artık gerçekten arka planda çalıştığını ve iş bitince
doğru sonucu ürettiğini kilitler. `ArchlenceApp.__new__` deseni
test_reset_flow.py'dekiyle aynı — MDApp.__init__ gerçek Window ister,
bu testler yalnızca ilgili metotların iş mantığını çalıştırdığı için
pencere kurmadan EventDispatcher'ı ayağa kaldırmak yeterli.
"""
import os
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")


class CryptoWarmupTest(unittest.TestCase):
    def test_returns_a_daemon_thread_and_warms_the_key_cache(self):
        from utils.crypto import DEFAULT_PASSWORD, _get_key
        _get_key.cache_clear()

        from main import ArchlenceApp
        thread = ArchlenceApp._warm_crypto_key_in_background()
        self.assertTrue(thread.daemon)
        thread.join(2)
        self.assertFalse(thread.is_alive())

        # Anahtar artık önbellekte olmalı: `_get_key`'i AYNI parametreyle
        # tekrar çağırmak PBKDF2'yi yeniden ÇALIŞTIRMAMALI (cache_info hit
        # sayısı artmalı). PR #22 (AEAD entegrasyonu) öncesinde bu,
        # `decrypt(encrypt(...))` round-trip'iyle dolaylı doğrulanıyordu —
        # ama `encrypt()` artık HER ZAMAN yeni AEAD şemasını ürettiği için
        # o round-trip `_get_key`'e hiç uğramaz oldu ve ısıtma sessizce
        # işlevsiz kalmıştı; bu test tam da o regresyonu yakaladı. Artık
        # `_get_key`'in kendisi doğrudan çağrılarak doğrulanıyor — var olan
        # her eski-format kaydın hâlâ bu yoldan geçtiği gerçeğine sadık
        # kalarak.
        before = _get_key.cache_info().hits
        _get_key(DEFAULT_PASSWORD)
        after = _get_key.cache_info().hits
        self.assertGreater(after, before)

    def test_does_not_block_the_caller(self):
        from utils.crypto import _get_key
        _get_key.cache_clear()

        from main import ArchlenceApp
        before = time.perf_counter()
        thread = ArchlenceApp._warm_crypto_key_in_background()
        elapsed = time.perf_counter() - before
        # Isıtma işleminin kendisi (soğuk PBKDF2) onlarca ms sürer; çağıranın
        # bunu BEKLEMEDEN dönmesi asıl hedef.
        self.assertLess(elapsed, 0.05)
        thread.join(2)


class FinancialAdvicePerformanceTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_patch = mock.patch("database.db.DB_NAME", self.db_path)
        self.db_patch.start()
        from database.init_db import initialize_database
        initialize_database()

    def tearDown(self):
        self.db_patch.stop()
        os.unlink(self.db_path)

    def _make_app(self):
        from main import ArchlenceApp
        app = ArchlenceApp.__new__(ArchlenceApp)
        app.language = "tr"
        app.root = None
        return app

    def test_generate_financial_advice_does_not_block_caller(self):
        app = self._make_app()
        before = time.perf_counter()
        thread = app.generate_financial_advice()
        elapsed = time.perf_counter() - before
        self.assertLess(elapsed, 0.05)
        self.assertTrue(thread.daemon)
        thread.join(2)
        self.assertFalse(thread.is_alive())

    def test_apply_is_skipped_for_a_stale_generation(self):
        """İkinci bir tazeleme başladıysa eski sonucun widget'a yazılmaması
        gerekir (update_metrics_and_goals'taki AYNI 'generation' deseni).

        Hesaplama bitip Clock geri çağrısı tetiklenmeden ÖNCE yeni bir
        tazelemenin başladığını simüle etmek için `_compute_financial_advice_text`
        gerçek hesabı yapar ama HEMEN ARDINDAN jenerasyonu ilerletir — tam
        olarak iki hızlı ardışık çağrının üreteceği durum."""
        app = self._make_app()
        app._apply_financial_advice_text = mock.Mock()

        original_compute = app._compute_financial_advice_text

        def compute_then_bump_generation():
            text = original_compute()
            app._advice_generation += 1
            return text

        app._compute_financial_advice_text = compute_then_bump_generation

        with mock.patch("main.Clock.schedule_once",
                         side_effect=lambda cb, *a: cb(0)):
            thread = app.generate_financial_advice()
            thread.join(2)

        app._apply_financial_advice_text.assert_not_called()

    def test_compute_financial_advice_text_reflects_real_transactions(self):
        """Salt hesaplama fonksiyonu doğru işlem verisinden doğru metni
        üretmeli — thread'leme, ALTINDAKİ mantığı bozmamalı."""
        from services.account_service import AccountService
        from services.transaction_service import TransactionService

        account_id = AccountService.create_account(
            "Test", "checking", initial_balance=10000,
        )
        TransactionService.add_transaction(
            account_id=account_id, amount=1000, transaction_type="income",
            category="Maaş", description="maaş",
        )
        TransactionService.add_transaction(
            account_id=account_id, amount=500, transaction_type="expense",
            category="Süpermarket", description="market",
        )

        app = self._make_app()
        text = app._compute_financial_advice_text()
        self.assertIn("Süpermarket", text)
        self.assertIn("%50.0", text)  # (1000-500)/1000 tasarruf oranı


class VacuumDatabasePerformanceTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_patch = mock.patch("database.db.DB_NAME", self.db_path)
        self.db_patch.start()
        from database.init_db import initialize_database
        initialize_database()

    def tearDown(self):
        self.db_patch.stop()
        os.unlink(self.db_path)

    def test_vacuum_runs_in_background_and_leaves_db_usable(self):
        from main import ArchlenceApp
        from database.db import get_connection

        app = ArchlenceApp.__new__(ArchlenceApp)
        before = time.perf_counter()
        thread = app.vacuum_database()
        elapsed = time.perf_counter() - before
        self.assertLess(elapsed, 0.05)
        thread.join(5)
        self.assertFalse(thread.is_alive())

        # VACUUM veritabanını bozmamalı; olağan bir sorgu hâlâ çalışmalı.
        conn = get_connection()
        row = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()
        conn.close()
        self.assertEqual(row[0], 0)


if __name__ == "__main__":
    unittest.main()
