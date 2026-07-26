import os
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo


ISTANBUL = ZoneInfo("Europe/Istanbul")


class PriceServiceTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_patch = mock.patch("database.db.DB_NAME", self.db_path)
        self.db_patch.start()
        from database.init_db import initialize_database
        initialize_database()

        from services import price_service
        with price_service._inflight_lock:
            price_service._inflight.clear()

    def tearDown(self):
        self.db_patch.stop()
        os.unlink(self.db_path)

    def test_bist_does_not_fetch_outside_market_hours(self):
        from services import price_service

        closed = datetime(2026, 7, 24, 20, 0, tzinfo=ISTANBUL)
        price_service._store_cache(
            {"ASELS": 245.5}, {"ASELS": "STOCK"},
            updated_at=closed - timedelta(days=2),
        )
        with (
            mock.patch.object(price_service, "_now", return_value=closed),
            mock.patch.object(price_service, "_download_batch") as download,
        ):
            value = price_service.get_price("ASELS", "STOCK")
        self.assertEqual(value, 245.5)
        download.assert_not_called()

    def test_never_cached_symbol_fetches_even_when_market_closed(self):
        """Hafta sonu eklenen bir hisse/altın/döviz sonsuza kadar 'Canlı veri
        bekleniyor…' durumunda kalmamalı — ilk çekim piyasa kapalıyken de
        denenmeli (bkz. fetch_prices_async'teki INFINITE_TTL istisnası)."""
        from services import price_service

        sunday = datetime(2026, 7, 26, 12, 0, tzinfo=ISTANBUL)
        with (
            mock.patch.object(price_service, "_now", return_value=sunday),
            mock.patch.object(
                price_service, "_download_batch",
                return_value={"SISE.IS": 43.42},
            ) as download,
        ):
            thread = price_service.fetch_prices_async(
                [("SISE", "STOCK")], None,
            )
            self.assertIsNotNone(thread)
            thread.join(2)
        download.assert_called_once()
        self.assertEqual(
            price_service.get_cached_price("SISE"), 43.42
        )

    def test_already_cached_symbol_still_skips_closed_market(self):
        """Fix, MEVCUT davranışı bozmamalı: cache'i olan bir sembol piyasa
        kapalıyken hâlâ atlanmalı (gereksiz istek göndermez)."""
        from services import price_service

        sunday = datetime(2026, 7, 26, 12, 0, tzinfo=ISTANBUL)
        price_service._store_cache(
            {"ASELS": 380.25}, {"ASELS": "STOCK"},
            updated_at=sunday - timedelta(days=2),
        )
        with (
            mock.patch.object(price_service, "_now", return_value=sunday),
            mock.patch.object(price_service, "_download_batch") as download,
        ):
            thread = price_service.fetch_prices_async(
                [("ASELS", "STOCK")], None,
            )
        self.assertIsNone(thread)
        download.assert_not_called()

    def test_ticker_mapper_normalizes_app_symbols(self):
        from utils.ticker_mapper import to_api_ticker

        self.assertEqual(to_api_ticker("ASELS", "Hisse"), "ASELS.IS")
        self.assertEqual(to_api_ticker("USD", "Döviz"), "USDTRY=X")
        self.assertEqual(to_api_ticker("BTC", "Kripto"), "BTC-USD")

    def test_crypto_cache_expires_after_three_minutes(self):
        from services import price_service

        now = datetime(2026, 7, 24, 12, 0, tzinfo=ISTANBUL)
        price_service._store_cache(
            {"BTC": 3_000_000}, {"BTC": "CRYPTO"},
            updated_at=now - timedelta(minutes=2, seconds=59),
        )
        with (
            mock.patch.object(price_service, "_now", return_value=now),
            mock.patch.object(price_service, "_download_batch") as download,
        ):
            thread = price_service.fetch_prices_async(
                [("BTC", "CRYPTO")], None
            )
        self.assertIsNone(thread)
        download.assert_not_called()

        price_service._store_cache(
            {"BTC": 3_000_000}, {"BTC": "CRYPTO"},
            updated_at=now - timedelta(minutes=3, seconds=1),
        )
        with (
            mock.patch.object(price_service, "_now", return_value=now),
            mock.patch.object(
                price_service, "_download_batch",
                return_value={"BTC-USD": 100_000, "USDTRY=X": 40},
            ) as download,
        ):
            thread = price_service.fetch_prices_async(
                [("BTC", "CRYPTO")], None
            )
            self.assertIsNotNone(thread)
            thread.join(1)
        download.assert_called_once()
        self.assertEqual(price_service.get_cached_price("BTC"), 4_000_000)

    def test_background_fetch_returns_without_blocking_ui_thread(self):
        from services import price_service

        started = threading.Event()
        release = threading.Event()

        def slow_download(_tickers):
            started.set()
            release.wait(1)
            return {"BTC-USD": 10, "USDTRY=X": 40}

        with mock.patch.object(
            price_service, "_download_batch", side_effect=slow_download
        ):
            before = time.perf_counter()
            thread = price_service.fetch_prices_async(
                [("BTC", "CRYPTO")], None, force_refresh=True
            )
            elapsed = time.perf_counter() - before
            self.assertLess(elapsed, 0.1)
            self.assertTrue(started.wait(0.5))
            self.assertTrue(thread.is_alive())
            self.assertTrue(thread.daemon)
            release.set()
            thread.join(1)
            self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
