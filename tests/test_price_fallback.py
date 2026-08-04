"""yfinance kesildiğinde devreye giren yedek fiyat sağlayıcıları.

Bu davranışın hiç testi yoktu çünkü davranışın kendisi yoktu: `_download_batch`
tek sağlayıcıya bağlıydı ve boş dönerse tüm portföy sessizce bayat cache'e
düşüyordu.

Testlerin odağı iki sözleşme:
  1. Yedek sağlayıcı yfinance'in BİRİM UZAYINDA konuşur — aşağı akıştaki
     TL'ye çevirme matematiği (USDTRY çarpımı, ons→gram) değişmeden çalışır.
  2. Fiyatın kaynağı DOĞRU raporlanır. Yedekten gelen bir fiyata "Yahoo
     Finance" demek kullanıcıya yanlış köken göstermek olurdu.
"""
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo


ISTANBUL = ZoneInfo("Europe/Istanbul")
# Hafta içi, BIST açık — TTL'in "piyasa kapalı" dalına düşmemek için.
WEEKDAY_NOON = datetime(2026, 7, 22, 12, 0, tzinfo=ISTANBUL)


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class PriceFallbackTest(unittest.TestCase):
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

    # ── Sağlayıcı birimleri ─────────────────────────────────────────────

    def test_coingecko_fallback_returns_usd_not_try(self):
        """KRİTİK: CoinGecko TRY de verebilir, ama yfinance USD veriyor.

        Yanlış birim döndürmek sessizce ~35x şişmiş bir portföy değeri üretir,
        çünkü aşağı akış sonucu ayrıca USDTRY ile çarpar.
        """
        from services import price_providers

        with mock.patch("requests.get", return_value=_Response(
                {"bitcoin": {"usd": 95_000.0}})) as get:
            out = price_providers.fetch_fallback_prices(["BTC-USD"])

        self.assertEqual(out["BTC-USD"], (95_000.0, "CoinGecko"))
        self.assertEqual(get.call_args.kwargs["params"]["vs_currencies"], "usd")

    def test_frankfurter_fallback_inverts_rate_to_try_per_unit(self):
        """Frankfurter `from=TRY` ile 1 TL'nin kaç USD ettiğini verir;
        istenen bunun tersi (1 USD kaç TL)."""
        from services import price_providers

        with mock.patch("requests.get", return_value=_Response(
                {"rates": {"USD": 0.025}})):
            out = price_providers.fetch_fallback_prices(["USDTRY=X"])

        price, source = out["USDTRY=X"]
        self.assertAlmostEqual(price, 40.0)
        self.assertEqual(source, "Frankfurter (ECB)")

    def test_uncovered_tickers_are_skipped_not_faked(self):
        """BIST ve GC=F için yedek YOK — belgelenmiş sınır."""
        from services import price_providers

        with mock.patch("requests.get") as get:
            out = price_providers.fetch_fallback_prices(["THYAO.IS", "GC=F"])

        self.assertEqual(out, {})
        get.assert_not_called()  # kapsam dışıysa ağa hiç çıkma

    def test_one_provider_failing_does_not_block_the_other(self):
        from services import price_providers
        import requests

        def _get(url, **_kwargs):
            if "coingecko" in url:
                raise requests.RequestException("down")
            return _Response({"rates": {"USD": 0.025}})

        with mock.patch("requests.get", side_effect=_get):
            out = price_providers.fetch_fallback_prices(
                ["BTC-USD", "USDTRY=X"])

        self.assertNotIn("BTC-USD", out)
        self.assertIn("USDTRY=X", out)  # kısmi sonuç > hiç sonuç

    # ── price_service ile bütünleşme ────────────────────────────────────

    def _fetch(self, symbols, yahoo_result, fallback_result):
        """Çekimi çalıştırır ve sonucu CACHE'ten okur.

        Callback'e bakılmıyor — `_schedule_callback` sonucu Kivy `Clock`'una
        kuyruklar ve test ortamında clock'u döndüren kimse yok, dolayısıyla
        callback hiç ateşlenmez. `tests/test_price_service.py` de aynı sebeple
        cache üzerinden doğruluyor.
        """
        from services import price_service

        with (
            mock.patch.object(price_service, "_now",
                              return_value=WEEKDAY_NOON),
            mock.patch.object(price_service, "_download_batch",
                              return_value=dict(yahoo_result)),
            mock.patch("services.price_providers.fetch_fallback_prices",
                       return_value=dict(fallback_result)),
        ):
            thread = price_service.fetch_prices_async(
                symbols, None, force_refresh=True)
            if thread is not None:
                thread.join(timeout=10)
        return price_service.get_cached_prices(
            [symbol for symbol, _kind in symbols])

    def test_fallback_fills_the_gap_yfinance_left(self):
        prices = self._fetch(
            [("BTC", "CRYPTO")],
            yahoo_result={"USDTRY=X": 40.0},          # kripto YOK
            fallback_result={"BTC-USD": (95_000.0, "CoinGecko")},
        )
        # 95_000 USD × 40 TL/USD — çevrim matematiği değişmeden çalışmalı.
        self.assertAlmostEqual(prices["BTC"], 3_800_000.0)

    def test_usdtry_fallback_rescues_crypto_conversion(self):
        """USDTRY kilit taşı: düşerse kripto DA altın DA fiyatlanamaz."""
        prices = self._fetch(
            [("BTC", "CRYPTO")],
            yahoo_result={"BTC-USD": 95_000.0},       # USDTRY YOK
            fallback_result={"USDTRY=X": (40.0, "Frankfurter (ECB)")},
        )
        self.assertAlmostEqual(prices["BTC"], 3_800_000.0)

    def test_no_fallback_call_when_yfinance_covered_everything(self):
        from services import price_service

        with (
            mock.patch.object(price_service, "_now",
                              return_value=WEEKDAY_NOON),
            mock.patch.object(price_service, "_download_batch",
                              return_value={"BTC-USD": 95_000.0,
                                            "USDTRY=X": 40.0}),
            mock.patch("services.price_providers.fetch_fallback_prices") as fb,
        ):
            thread = price_service.fetch_prices_async(
                [("BTC", "CRYPTO")], None, force_refresh=True)
            if thread is not None:
                thread.join(timeout=10)
        fb.assert_not_called()

    # ── Kaynak raporlama ────────────────────────────────────────────────

    def test_status_reports_the_provider_that_actually_answered(self):
        from services import price_service

        self._fetch(
            [("BTC", "CRYPTO")],
            yahoo_result={"USDTRY=X": 40.0},
            fallback_result={"BTC-USD": (95_000.0, "CoinGecko")},
        )
        status = price_service.get_price_status(
            "BTC", "CRYPTO", now=WEEKDAY_NOON)
        # Fiyat İKİ ticker'ın çarpımı; ikisi farklı sağlayıcıdan geldi.
        self.assertEqual(status.source, "CoinGecko + Yahoo Finance")

    def test_status_stays_yahoo_when_yahoo_answered(self):
        from services import price_service

        self._fetch(
            [("BTC", "CRYPTO")],
            yahoo_result={"BTC-USD": 95_000.0, "USDTRY=X": 40.0},
            fallback_result={},
        )
        status = price_service.get_price_status(
            "BTC", "CRYPTO", now=WEEKDAY_NOON)
        self.assertEqual(status.source, "Yahoo Finance")

    # ── Migration ───────────────────────────────────────────────────────

    def test_rows_written_before_the_source_column_read_back_as_yahoo(self):
        """Eski profillerde `source` sütunu yok. O satırlar yfinance'ten
        gelmişti (o dönemde tek sağlayıcı oydu), öyle raporlanmalı — ve
        sütunun eklenmesi mevcut veriyi kaybetmemeli."""
        from services import price_service

        # Sütunu düşürüp sürüm-öncesi durumu birebir kur.
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DROP TABLE IF EXISTS asset_price_cache")
            conn.execute("""
                CREATE TABLE asset_price_cache (
                    symbol TEXT PRIMARY KEY,
                    price REAL NOT NULL,
                    asset_type TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute(
                "INSERT INTO asset_price_cache VALUES (?, ?, ?, ?)",
                ("ASELS", 245.5, "STOCK", WEEKDAY_NOON.isoformat()),
            )

        status = price_service.get_price_status(
            "ASELS", "STOCK", now=WEEKDAY_NOON)
        self.assertEqual(status.source, "Yahoo Finance")
        self.assertIsNotNone(status.price)  # veri kaybolmadı

        with sqlite3.connect(self.db_path) as conn:
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(asset_price_cache)")
            }
        self.assertIn("source", columns)


if __name__ == "__main__":
    unittest.main()
