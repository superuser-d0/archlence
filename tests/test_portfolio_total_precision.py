"""Portföy piyasa değeri toplamı kuruşu kaybetmemeli.

NEDEN VAR: `fetch_active_non_try_total` her varlığın değerini
`float(quantity) * float(price)` ile hesaplayıp float bir akümülatörde
topluyordu. `calculate_pnl`'de kapatılan sınıfın aynısı: çarpım yuvarlama
sınırına düştüğünde ikili gösterim yarım kuruşu yutuyor.

Ölçülerek doğrulandı, ve önemli olan
şu: bu vakalar uydurma değil, Archlence'in KENDİ hassasiyet politikası
içinde — kripto miktarı 8 hane, hisse 6 hane, fiyatlar iki-üç ondalık.

    15 kripto x 0,045 TL       = 0,675  ->  0,67 gösteriliyordu, 0,68 olmalı
    3 hisse   x 1,005 TL       = 3,015  ->  3,01 gösteriliyordu, 3,02 olmalı
    0,00000015 x 4.500.000 TL  = 0,675  ->  0,67 gösteriliyordu, 0,68 olmalı

Testler helper'ı değil GERÇEK YOLU sürüyor: varlıklar veritabanına yazılır,
fiyat cache'i doldurulur, `fetch_active_non_try_total` çağrılır ve
callback'in verdiği sonuç okunur.
"""

import os
import tempfile
import threading
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock


class PortfolioTotalPrecision(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="archlence-porttotal-")
        root = Path(self.tempdir.name)
        self.db_path = root / "finance.db"
        self.db_patch = mock.patch("database.db.DB_NAME", str(self.db_path))
        self.key_patch = mock.patch(
            "utils.crypto._get_aead_key", return_value=os.urandom(32)
        )
        self.db_patch.start()
        self.key_patch.start()
        self.addCleanup(self.tempdir.cleanup)
        self.addCleanup(self.db_patch.stop)
        self.addCleanup(self.key_patch.stop)

        from database.init_db import initialize_database
        initialize_database()


    def _add_asset(self, name, code, kind, price, quantity):
        from database.db import insert_asset
        insert_asset(name, code, kind, price, quantity)

    def _total_for(self, assets, prices):
        """assets: [(ad, kod, tur, alis, miktar)] · prices: {kod: fiyat}

        Fiyat cache'i doğrudan yazılır; ağ yok. `fetch_active_non_try_total`
        arka planda thread açtığı için sonuç bir Event ile beklenir.
        """
        for asset in assets:
            self._add_asset(*asset)

        import services.asset_service as asset_service

        done = threading.Event()
        captured = {}

        def callback(result):
            captured.update(result)
            done.set()

        with mock.patch(
            "services.price_service.get_cached_prices", return_value=dict(prices)
        ), mock.patch("services.price_service.fetch_prices_async", return_value=None):
            asset_service.fetch_active_non_try_total(callback)
            self.assertTrue(done.wait(timeout=10), "toplam hesabı zamanında bitmedi")
        return captured

    def _assert_total_kurus(self, result, expected):
        """Gösterilen kuruş, tam Decimal sonucun kuruşuna eşit olmalı.

        Karşılaştırma UI'ın kullandığı biçimleme üzerinden yapılıyor
        (`account_mixin._fmt` -> `f"{value:,.2f}"`), çünkü kullanıcının
        gördüğü sayı bu. Servisin `total` alanını ham okumak, sınırdaki
        hatayı gizleyebilirdi.
        """
        shown = f"{result['total']:,.2f}"
        self.assertEqual(
            shown, expected,
            f"gösterilen toplam {shown}, beklenen {expected} "
            f"(ham değer: {result['total']!r})",
        )


    def test_crypto_quantity_times_sub_kurus_price(self):
        """15 x 0,045 = 0,675 -> 0,68."""
        result = self._total_for(
            [("Coin", "AAA-USD", "Kripto", 0.045, 15.0)],
            {"AAA-USD": 0.045},
        )
        self._assert_total_kurus(result, "0.68")

    def test_equity_quantity_times_fractional_price(self):
        """3 x 1,005 = 3,015 -> 3,02."""
        result = self._total_for(
            [("Hisse", "BBB", "Hisse", 1.005, 3.0)],
            {"BBB": 1.005},
        )
        self._assert_total_kurus(result, "3.02")

    def test_high_precision_crypto_quantity_times_large_price(self):
        """0,00000015 x 4.500.000 = 0,675 -> 0,68."""
        result = self._total_for(
            [("Coin", "CCC-USD", "Kripto", 1.0, 0.00000015)],
            {"CCC-USD": 4_500_000.0},
        )
        self._assert_total_kurus(result, "0.68")


    def test_ten_assets_match_the_decimal_reference(self):
        assets, prices, reference = [], {}, Decimal(0)
        for index in range(10):
            code = f"D{index:02d}"
            quantity = Decimal("0.045") * (index + 1)
            price = Decimal("15.005")
            assets.append(("Coin", code, "Kripto", float(price), float(quantity)))
            prices[code] = float(price)
            reference += quantity * price
        result = self._total_for(assets, prices)
        self._assert_total_kurus(
            result, f"{reference.quantize(Decimal('0.01')):,.2f}")

    def test_hundred_assets_match_the_decimal_reference(self):
        assets, prices, reference = [], {}, Decimal(0)
        for index in range(100):
            code = f"E{index:03d}"
            quantity = Decimal("0.00000015") * (index + 1)
            price = Decimal("4500000.00")
            assets.append(("Coin", code, "Kripto", 1.0, float(quantity)))
            prices[code] = float(price)
            reference += quantity * price
        result = self._total_for(assets, prices)
        self._assert_total_kurus(
            result, f"{reference.quantize(Decimal('0.01')):,.2f}")


    def test_progress_and_final_totals_agree(self):
        """Son ara toplam ile nihai toplam AYNI finansal değeri göstermeli.

        Korunan şey "bit bit aynı akümülatör" değil — o yalnız eski
        uygulamanın bir ayrıntısıydı. Sözleşme, ikisinin aynı parayı temsil
        etmesi; ikisi de aynı dönüşümden geçmeli.
        """
        import services.asset_service as asset_service

        for index in range(3):
            self._add_asset("Coin", f"F{index}", "Kripto", 0.045, 15.0)

        seen = []
        done = threading.Event()
        final = {}

        def progress(result):
            seen.append(result)

        def callback(result):
            final.update(result)
            done.set()

        prices = {f"F{index}": 0.045 for index in range(3)}
        with mock.patch(
            "services.price_service.get_cached_prices", return_value=prices
        ), mock.patch("services.price_service.fetch_prices_async", return_value=None):
            asset_service.fetch_active_non_try_total(callback, progress)
            self.assertTrue(done.wait(timeout=10))

        self.assertTrue(seen, "hiç progress olayı gelmedi")
        self.assertEqual(seen[0]["total"], 0.0, "ilk progress 0,0 olmalı")
        self.assertIsInstance(final["total"], float, "public tip float kalmalı")
        for event in seen:
            self.assertIsInstance(event["total"], float)
        self.assertEqual(
            f"{seen[-1]['total']:,.2f}", f"{final['total']:,.2f}",
            "son ara toplam ile nihai toplam aynı parayı göstermiyor",
        )
        self.assertEqual(final["priced_count"], 3)
        self.assertEqual(final["asset_count"], 3)

    def test_a_non_finite_price_does_not_kill_the_background_thread(self):
        """Sonsuz fiyat TEORİK DEĞİL: mevcut filtre onu geçiriyor.

        `_fetch_live_try_prices` ve `price_providers` fiyatı
        `if value is not None and float(value) > 0` ile eliyor — ve
        `float("inf") > 0` DOĞRU'dur. Yani bozuk bir sağlayıcıdan gelen
        sonsuz fiyat cache'e yazılabilir.

        Toplam artık `decimal_from()` kullanıyor ve o sonlu olmayan değerde
        `ValueError` fırlatır. Bu döngü arka plan thread'inde koşuyor ve
        korumasız; istisna dışarı sızsaydı callback hiç çağrılmaz, arayüz de
        sonsuza kadar beklerdi. Bozuk varlık, fiyatlanamayan varlıkla aynı
        şekilde atlanmalı ve GERİ KALAN toplam doğru gelmeli.
        """
        result = self._total_for(
            [("Coin", "H01", "Kripto", 0.045, 15.0),
             ("Bozuk", "H02", "Kripto", 1.0, 1.0)],
            {"H01": 0.045, "H02": float("inf")},
        )
        self._assert_total_kurus(result, "0.68")
        self.assertEqual(result["priced_count"], 1, "bozuk varlık sayılmamalı")
        self.assertEqual(result["asset_count"], 2)
        self.assertTrue(result["complete"], "callback tamamlanmadan döndü")

    def test_unpriced_assets_are_skipped_without_breaking_the_total(self):
        result = self._total_for(
            [("Coin", "G01", "Kripto", 0.045, 15.0),
             ("Coin", "G02", "Kripto", 1.0, 1.0)],
            {"G01": 0.045},
        )
        self._assert_total_kurus(result, "0.68")
        self.assertEqual(result["priced_count"], 1)
        self.assertEqual(result["asset_count"], 2)


if __name__ == "__main__":
    unittest.main()
