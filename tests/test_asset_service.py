"""services/asset_service canlı portföy motoru için ağ gerektirmeyen testler.

Odak: 'Aktif Varlıklarım' satırının ₺0,00 kalmasına yol açan sembol
eşleşmesi hatası. Depoda kripto kodu 'BTC-USD', döviz kodu 'USDTRY=X'
biçiminde tutulur; CoinGecko/Frankfurter eşleştirmesi bunları çözebilmelidir.
Ağ çağrıları mock'lanır, böylece testler deterministiktir.
"""
import os
import tempfile
import unittest
from unittest import mock


class SymbolNormalizationTests(unittest.TestCase):
    def test_coingecko_id_strips_quote_suffix(self):
        from services.asset_service import _coingecko_id_for
        self.assertEqual(_coingecko_id_for("BTC-USD"), "bitcoin")
        self.assertEqual(_coingecko_id_for("ETH-USD"), "ethereum")
        self.assertEqual(_coingecko_id_for("ETC-USD"), "ethereum-classic")
        self.assertEqual(_coingecko_id_for("SOL-USDT"), "solana")
        self.assertEqual(_coingecko_id_for("btc"), "bitcoin")  # bare + lowercase

    def test_coingecko_id_none_for_non_crypto(self):
        from services.asset_service import _coingecko_id_for
        for code in ("THYAO.IS", "GC=F", "USDTRY=X", "", None):
            self.assertIsNone(_coingecko_id_for(code))

    def test_frankfurter_base_for_try_pairs_and_bare(self):
        from services.asset_service import _frankfurter_base_for
        self.assertEqual(_frankfurter_base_for("USDTRY=X"), "USD")
        self.assertEqual(_frankfurter_base_for("EURTRY=X"), "EUR")
        self.assertEqual(_frankfurter_base_for("USD"), "USD")

    def test_frankfurter_base_none_for_non_try_or_crypto(self):
        from services.asset_service import _frankfurter_base_for
        # TRY dışı çapraz kur yanlış fiyatlanmasın diye elenir.
        for code in ("GBPUSD=X", "BTC-USD", "GC=F", "", None):
            self.assertIsNone(_frankfurter_base_for(code))


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class LivePriceMatchingTests(unittest.TestCase):
    """_fetch_live_try_prices depodaki TAM kodu anahtar olarak korumalı."""

    def _fake_get(self, url, params=None, timeout=None):
        if "coingecko" in url:
            return _FakeResponse({
                "bitcoin": {"try": 3_000_000.0},
                "ethereum": {"try": 90_000.0},
            })
        if "frankfurter" in url:
            # TRY -> {USD, EUR}: 1 TRY = 0.02 USD => 1 USD = 50 TRY
            return _FakeResponse({"rates": {"USD": 0.02, "EUR": 0.018}})
        raise AssertionError(f"unexpected url {url}")

    def test_crypto_and_fiat_keyed_by_full_code(self):
        from services import asset_service
        assets = [
            {"asset_code": "BTC-USD", "asset_type": "Kripto", "quantity": 0.01, "purchase_price": 1.0},
            {"asset_code": "ETH-USD", "asset_type": "Kripto", "quantity": 1.0, "purchase_price": 1.0},
            {"asset_code": "USDTRY=X", "asset_type": "Döviz", "quantity": 100.0, "purchase_price": 1.0},
            {"asset_code": "EURTRY=X", "asset_type": "Döviz", "quantity": 100.0, "purchase_price": 1.0},
        ]
        with mock.patch("requests.get", side_effect=self._fake_get):
            prices = asset_service._fetch_live_try_prices(assets)
        # Anahtar TAM kod olmalı (eski hata: hiç eşleşmiyordu -> {}).
        self.assertEqual(prices["BTC-USD"], 3_000_000.0)
        self.assertEqual(prices["ETH-USD"], 90_000.0)
        self.assertAlmostEqual(prices["USDTRY=X"], 50.0)          # 1/0.02
        self.assertAlmostEqual(prices["EURTRY=X"], 1.0 / 0.018)

    def test_raises_when_all_services_fail_and_nothing_priced(self):
        import requests
        from services import asset_service
        assets = [{"asset_code": "BTC-USD", "asset_type": "Kripto", "quantity": 1.0, "purchase_price": 1.0}]
        with mock.patch("requests.get", side_effect=requests.RequestException("offline")):
            with self.assertRaises(RuntimeError):
                asset_service._fetch_live_try_prices(assets)


class NonTryFilterAndCacheTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()
        from database.init_db import initialize_database
        initialize_database()
        # Demo tohumu TL dışı varlıklar da içerir; testi izole tutmak için
        # active_assets tablosunu boşaltıp kendi kayıtlarımızı ekliyoruz.
        from database.db import get_connection
        conn = get_connection()
        conn.execute("DELETE FROM active_assets")
        conn.commit()
        conn.close()

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def test_get_active_non_try_assets_excludes_try_and_nonpositive(self):
        from database.db import insert_asset
        from services.asset_service import get_active_non_try_assets
        insert_asset("Bitcoin", "BTC-USD", "Kripto", 1.0, 0.5)
        insert_asset("Türk Lirası", "TRY", "Döviz", 1.0, 1000.0)     # elenir (TRY)
        insert_asset("Nakit TL", "TL", "Döviz", 1.0, 500.0)          # elenir (TL)
        insert_asset("Bos", "ETH-USD", "Kripto", 1.0, 0.0)           # elenir (qty=0)
        codes = [a["asset_code"] for a in get_active_non_try_assets()]
        self.assertIn("BTC-USD", codes)
        self.assertNotIn("TRY", codes)
        self.assertNotIn("TL", codes)
        self.assertNotIn("ETH-USD", codes)  # miktarı 0

    def test_price_cache_round_trip(self):
        from services.asset_service import _store_prices, _read_cached_prices
        _store_prices({"BTC-USD": 3_000_000.0, "USDTRY=X": 50.0})
        cached = _read_cached_prices({"BTC-USD", "USDTRY=X", "YOK"})
        self.assertEqual(cached["BTC-USD"], 3_000_000.0)
        self.assertEqual(cached["USDTRY=X"], 50.0)
        self.assertNotIn("YOK", cached)


class FallbackToCacheTests(unittest.TestCase):
    """Canlı servis çökerse önbellekteki son fiyatla toplam yine hesaplanmalı."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch("database.db.DB_NAME", self.db_path)
        self._patcher.start()
        from database.init_db import initialize_database
        initialize_database()
        from database.db import get_connection, insert_asset
        conn = get_connection()
        conn.execute("DELETE FROM active_assets")
        conn.commit()
        conn.close()
        insert_asset("Bitcoin", "BTC-USD", "Kripto", 1_000_000.0, 2.0)

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def test_uses_cached_price_when_live_fetch_fails(self):
        import threading
        from services import asset_service
        # Önce önbelleğe son bilinen fiyatı yaz.
        asset_service._store_prices({"BTC-USD": 3_000_000.0})
        done = threading.Event()
        out = {}

        def _fail(_assets):
            raise RuntimeError("offline")

        # Canlı fiyat ve yfinance yedeği başarısız; yalnızca önbellek kalır.
        with mock.patch.object(asset_service, "_fetch_live_try_prices", _fail), \
             mock.patch.object(asset_service, "fetch_current_price", return_value=None):
            asset_service.fetch_active_non_try_total(lambda r: (out.update(r), done.set()))
            self.assertTrue(done.wait(10))

        self.assertEqual(out["asset_count"], 1)
        self.assertEqual(out["priced_count"], 1)
        self.assertEqual(out["cached_count"], 1)
        self.assertAlmostEqual(out["total"], 2.0 * 3_000_000.0)  # qty * cached price


if __name__ == "__main__":
    unittest.main()
