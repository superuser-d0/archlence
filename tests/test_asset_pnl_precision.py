"""`calculate_pnl` davranış kilidi ve precision regresyonu.

NEDEN VAR: bu fonksiyonun HİÇ testi yoktu. Portföy ekranındaki kâr/zarar,
güncel değer ve maliyet sayılarının tamamını üretiyor ve dört ardışık ikili
kayan nokta işlemi yapıp sonunda `round(..., 2)` uyguluyordu.

İki sınıf bilerek ayrı:

  * `PnlBehaviourLock` — Decimal geçişinin DEĞİŞTİRMEMESİ gereken her şey.
    Bu testler geçişten ÖNCE de sonra da aynı sonucu vermeli; geçişin
    "davranışı koruyor" iddiasının kanıtı bunlar.

  * `PnlBinaryArtefact` — geçişin DÜZELTMESİ beklenen kuruş hataları. Bunlar
    geçişten önce KIRMIZI, sonra yeşil. Bir migration'ın gerçekten bir şey
    kazandırdığını gösteren tek dürüst yol, kazancın önce kırmızı bir test
    olarak yazılmasıdır.

`signal` kararının ham (yuvarlanmamış) orandan verildiğine dikkat: yuvarlanmış
yüzdeye geçmek, 0,004 oranında kâr eden bir varlığı "başabaş" gösterirdi.
`test_signal_comes_from_the_unrounded_ratio` bunu kilitliyor.
"""

import unittest

from services.asset_service import calculate_pnl


class PnlBehaviourLock(unittest.TestCase):
    """Decimal geçişi bu değerlerin HİÇBİRİNİ değiştirmemeli."""

    def test_profit_case(self):
        result = calculate_pnl(150.0, 100.0, 10.0)
        self.assertEqual(result["total_cost"], 1000.0)
        self.assertEqual(result["total_value"], 1500.0)
        self.assertEqual(result["pnl_amount"], 500.0)
        self.assertEqual(result["pnl_pct"], 50.0)
        self.assertEqual(result["signal"], "profit")

    def test_loss_case(self):
        result = calculate_pnl(80.0, 100.0, 10.0)
        self.assertEqual(result["total_cost"], 1000.0)
        self.assertEqual(result["total_value"], 800.0)
        self.assertEqual(result["pnl_amount"], -200.0)
        self.assertEqual(result["pnl_pct"], -20.0)
        self.assertEqual(result["signal"], "loss")

    def test_breakeven_case(self):
        result = calculate_pnl(100.0, 100.0, 10.0)
        self.assertEqual(result["pnl_amount"], 0.0)
        self.assertEqual(result["pnl_pct"], 0.0)
        self.assertEqual(result["signal"], "breakeven")

    def test_zero_purchase_price_reports_breakeven_despite_a_gain(self):
        """Mevcut davranışın TUHAFLIĞI, ve bilerek korunuyor.

        `purchase_price = 0` bir oran tanımlamıyor (sıfıra bölme), kod da
        oranı 0,0 sayıp "başabaş" diyor — oysa `pnl_amount` 1.500 TL. Bu
        yanıltıcı olabilir ama DEĞİŞTİRMEK bu PR'ın işi değil: precision
        geçişi ile ürün kararını aynı commit'e karıştırmak, ikisinin de
        gözden geçirilmesini zorlaştırır. Test, geçişin bunu kazara
        değiştirmediğini garanti ediyor.
        """
        result = calculate_pnl(150.0, 0.0, 10.0)
        self.assertEqual(result["total_cost"], 0.0)
        self.assertEqual(result["total_value"], 1500.0)
        self.assertEqual(result["pnl_amount"], 1500.0)
        self.assertEqual(result["pnl_pct"], 0.0)
        self.assertEqual(result["signal"], "breakeven")

    def test_high_precision_quantity_rounds_money_to_zero(self):
        """Kripto miktarı (1e-8) — para alanları kuruşta sıfırlanır, oran kalır."""
        result = calculate_pnl(250.0, 200.0, 0.00000001)
        self.assertEqual(result["total_cost"], 0.0)
        self.assertEqual(result["total_value"], 0.0)
        self.assertEqual(result["pnl_amount"], 0.0)
        self.assertEqual(result["pnl_pct"], 25.0)
        self.assertEqual(result["signal"], "profit")

    def test_large_but_valid_values(self):
        result = calculate_pnl(1e9, 999999999.0, 1000.0)
        self.assertEqual(result["total_value"], 1000000000000.0)
        self.assertEqual(result["total_cost"], 999999999000.0)
        self.assertEqual(result["pnl_amount"], 1000.0)
        self.assertEqual(result["signal"], "profit")

    def test_signal_comes_from_the_unrounded_ratio(self):
        """Oran yüzdenin ikinci hanesinin ALTINDA kalsa bile kâr kârdır.

        1e9 / 999.999.999 oranı %0,0000001 — yuvarlanınca 0,00 görünür ama
        `signal` "profit" kalmalı. Karar yuvarlanmış yüzdeye taşınırsa bu
        test kırılır.
        """
        result = calculate_pnl(1e9, 999999999.0, 1000.0)
        self.assertEqual(result["pnl_pct"], 0.0)
        self.assertEqual(result["signal"], "profit")

    def test_production_shaped_inputs_return_floats(self):
        """Gerçek çağıranlar hep float veriyor; dönüş de float kalmalı.

        `asset["purchase_price"]` ve `asset["quantity"]` `float(decrypt(...))`
        ile üretiliyor, `current_price` ise REAL sütundan geliyor — yani
        üretimde üç girdi de float. UI ve cache bu tipe göre yazılmış.
        """
        result = calculate_pnl(150.0, 100.0, 10.0)
        for key in ("pnl_amount", "pnl_pct", "total_value", "total_cost"):
            self.assertIsInstance(result[key], float, f"{key} float olmalı")
        self.assertIsInstance(result["signal"], str)


class PnlBinaryArtefact(unittest.TestCase):
    """Geçişten ÖNCE kırmızı, sonra yeşil: kazancın kanıtı."""

    def test_sub_kurus_unit_price_does_not_lose_a_kurus(self):
        """0,045 x 15 = 0,675 — kuruşa yuvarlanınca 0,68 olmalı.

        İkili kayan noktada 0.045*15 = 0.6749999999999999 çıkıyor ve
        `round()` bunu 0,67'ye indiriyor. Bir kuruş, ama kaynağı temsil
        hatası: kullanıcının girdiği sayı 0,045 idi, 0,04499999... değil.
        `Decimal(str(...))` girdiyi yazıldığı gibi alır.
        """
        result = calculate_pnl(0.05, 0.045, 15.0)
        self.assertEqual(result["total_cost"], 0.68)

    def test_fractional_unit_price_keeps_the_half_kurus(self):
        """1,005 x 3 = 3,015 — politikaya göre 3,02.

        BU TEST BİR HATAMIN KAYDI: bu vakayı önce "korunacak davranış" diye
        yazdım ve beklentiyi mevcut çıktıdan (3,01) aldım. Yanlıştı — mevcut
        çıktının kendisi artefaktın ta kendisiydi: ikili gösterimde
        1.005*3 = 3.0149999999999997 olduğu için `round()` sınırı hiç
        görmüyordu. Mevcut davranışı ölçüp beklenti diye yazmak, hatayı
        sözleşmeye dönüştürmenin en kolay yolu; karakterizasyon testi
        yazarken ölçülen değerin TAM sonuç olup olmadığı ayrıca kontrol
        edilmeli.
        """
        result = calculate_pnl(1.005, 1.0, 3.0)
        self.assertEqual(result["total_cost"], 3.0)
        self.assertEqual(result["total_value"], 3.02)
        self.assertEqual(result["pnl_amount"], 0.02)
        self.assertEqual(result["pnl_pct"], 0.5)
        self.assertEqual(result["signal"], "profit")

    def test_half_cent_boundary_rounds_by_policy_not_by_representation(self):
        """2,675 tam olarak yarım kuruş sınırında.

        Politikamız ROUND_HALF_EVEN (`utils/financial_decimal.py`) ve 2,675
        için sonuç 2,68. `round()` de HALF_EVEN kullanır — fark modda değil,
        GİRDİDE: float 2.675 aslında 2.67499999... olduğu için `round()`
        sınırı hiç görmez ve 2,67 verir.
        """
        result = calculate_pnl(3.0, 2.675, 1.0)
        self.assertEqual(result["total_cost"], 2.68)


class PnlNonFiniteInput(unittest.TestCase):
    """Tek BİLİNÇLİ davranış değişikliği, ayrı sınıfta duruyor.

    Eskiden sonlu olmayan girdi sessizce `nan`/`inf` döndürüyordu — üstelik
    `nan` için "başabaş", `inf` için "kâr" diyerek. İkisi de ekrana ve
    `total +=` toplamalarına sızıyordu; v0.0.9'un yazma yolunda kapattığı
    bozulma sınıfının okuma tarafındaki hâli.

    Fırlatmak SEÇENEK DEĞİLDİ: `asset_service.load_assets_with_prices` ve
    `price_service.enrich_assets_from_cache` bu çağrıyı korumasız bir döngüde
    yapıyor, yani tek bozuk satır TÜM portföy yüklemesini düşürürdü. Bunun
    yerine, çağıranların fiyatlanamayan varlık için ZATEN ürettiği ve
    işlediği biçim döndürülüyor.
    """

    def _assert_error_shape(self, result):
        self.assertEqual(result["signal"], "error")
        for key in ("pnl_amount", "pnl_pct", "total_value", "total_cost"):
            self.assertIsNone(result[key], f"{key} None olmalı")

    def test_nan_price_no_longer_reports_breakeven(self):
        self._assert_error_shape(calculate_pnl(float("nan"), 100.0, 10.0))

    def test_infinite_quantity_no_longer_reports_profit(self):
        self._assert_error_shape(calculate_pnl(150.0, 100.0, float("inf")))

    def test_missing_value_does_not_raise(self):
        """Eskiden `TypeError` fırlatıyordu; döngüyü yine düşürürdü."""
        self._assert_error_shape(calculate_pnl(150.0, None, 10.0))


if __name__ == "__main__":
    unittest.main()
