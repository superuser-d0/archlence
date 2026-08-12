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
        from database.db import SECRET_KEY, get_connection, insert_asset
        from services.asset_service import get_active_non_try_assets
        from utils.crypto import encrypt
        insert_asset("Bitcoin", "BTC-USD", "Kripto", 1.0, 0.5)
        insert_asset("Türk Lirası", "TRY", "Döviz", 1.0, 1000.0)     # elenir (TRY)
        insert_asset("Nakit TL", "TL", "Döviz", 1.0, 500.0)          # elenir (TL)
        # SIFIR MİKTARLI SATIR DOĞRUDAN SQL İLE yazılıyor: `insert_asset`
        # artık sıfır/negatif miktarı reddediyor (üretim yolu
        # `create_purchase` da öyle) ve satış tamamen boşalan varlığı
        # SİLİYOR. Yani böyle bir satır ancak ESKİ bir yapının ya da
        # dışarıdan düzenlemenin mirasıdır — ve okuma tarafının onu elemesi
        # tam olarak bu yüzden hâlâ ölçülmesi gereken bir davranış.
        conn = get_connection()
        conn.execute(
            "INSERT INTO active_assets (asset_name, asset_code, asset_type,"
            " purchase_price, quantity, purchase_date)"
            " VALUES (?,?,?,?,?,?)",
            ("Bos", "ETH-USD", "Kripto", encrypt("1.0", SECRET_KEY),
             encrypt("0.0", SECRET_KEY), "2026-01-01 00:00:00"),
        )
        conn.commit()
        conn.close()
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


class Bist100PriceParsingTests(unittest.TestCase):
    """`fetch_bist100_prices`'ın hücre başına hata dalı.

    Bu dalın hiç testi yoktu. Geniş `except Exception` ölçülmüş dört tipe
    (`KeyError, IndexError, TypeError, ValueError`) daraltıldı; test o kümenin
    diş taşıdığını, yani her birinin GERÇEKTEN oluştuğunu kanıtlar. Kümeden
    biri çıkarılırsa thread istisnayı dış bloğa taşır, sağlam kodlar da
    kaybolur ve testler kırılır.
    """

    def _run(self, codes, fake_download):
        """Toplu çekmeyi çalıştırır; (fiyatlar, dış-blok-hata-logladı-mı) döner.

        İkinci değer kritik: hücre içi hata dalı kümesinden bir tip
        çıkarıldığında istisna DIŞ `except Exception`'a kaçar ve orada
        `_log().error(...)` düşer. Dış blok yakaladığı için `callback` yine
        çağrılır; yani yalnızca sonuç sözlüğüne bakan bir test daralmanın
        yanlış olduğunu GÖREMEZ (ilk yazımda böyleydi, dişsizdi).
        """
        import logging
        import threading
        from services import asset_service

        done = threading.Event()
        out = {}
        logger = logging.getLogger("archlence")
        with mock.patch.dict(
            "sys.modules",
            {"yfinance": mock.Mock(download=fake_download)},
        ), mock.patch.object(logger, "error") as fake_error:
            asset_service.fetch_bist100_prices(
                codes, lambda p: (out.update(p), done.set()))
            self.assertTrue(done.wait(10))
        return out, fake_error.called

    def test_broken_cells_are_skipped_and_sound_ones_survive(self):
        import numpy as np
        import pandas as pd

        # Bozulma biçimleri:
        #   THYAO.IS -> NaN  (hata değil, math.isnan ile eleniyor)
        #   GARAN.IS -> None (TypeError)
        #   BAD.IS   -> metin (ValueError)
        #   YOK.IS   -> sütun hiç yok (KeyError)
        # AKBNK BİLEREK EN SONDA: bir tip kümeden düşerse döngü ondan önce
        # kırılır ve sağlam fiyat da kaybolur.
        row = pd.Series({
            "AKBNK.IS": 42.5,
            "THYAO.IS": np.nan,
            "GARAN.IS": None,
            "BAD.IS": "n/a",
        })

        prices, outer_error = self._run(
            ["THYAO", "GARAN", "BAD", "YOK", "AKBNK"],
            lambda *a, **k: _FrameStub(row),
        )
        # Bozuk hücreler sessizce elenmeli, SONRAKİ sağlam kod yine fiyatlanmalı.
        self.assertEqual(prices, {"AKBNK": 42.5})
        self.assertFalse(outer_error, "hücre hatası dış bloğa kaçmamalı")

    def test_single_ticker_scalar_shape_does_not_kill_the_batch(self):
        """yf.download TEK ticker'da Series yerine skaler döndürüyor.

        Ölçüldü: `scalar['AKBNK.IS']` -> IndexError ("invalid index to scalar
        variable"). Küme bu tipi içermezse istisna dış bloğa kaçar; sonuç
        sözlüğü yine boş olduğu için FARK yalnızca dış blokta düşen hata
        kaydından anlaşılır.
        """
        import numpy as np

        prices, outer_error = self._run(
            ["AKBNK", "THYAO"],
            lambda *a, **k: _FrameStub(np.float64(42.5)),
        )
        self.assertEqual(prices, {})  # çökmeden, boş ama TAMAMLANMIŞ sonuç
        self.assertFalse(outer_error, "skaler şekil dış bloğa kaçmamalı")


class _FrameStub:
    """`data["Close"].iloc[-1]` erişimini taklit eden asgari yfinance stub'ı."""

    def __init__(self, last_row):
        self._last_row = last_row

    def __getitem__(self, key):
        assert key == "Close"
        return self

    @property
    def iloc(self):
        return _IlocStub(self._last_row)


class _IlocStub:
    def __init__(self, last_row):
        self._last_row = last_row

    def __getitem__(self, index):
        assert index == -1
        return self._last_row


if __name__ == "__main__":
    unittest.main()
