"""CSV içe aktarımının sayısal doğrulaması.

Denetimde bulunan hata: `parse_transactions_csv` tutarı `float(raw)` ile
ayrıştırıp yalnızca `amount <= 0` kontrolü yapıyordu. `float("inf")` ve
`float("nan")` İKİSİ de Python'da sorunsuz ayrıştırılır ve İKİSİ de bu
kontrolü GEÇER (IEEE 754: nan ile yapılan her karşılaştırma False'tur,
inf zaten <= 0 değildir). Böyle tek bir satır içeri alınınca
`adjust_account_balance`'ın `balance = balance + ?` işlemi hesabı kalıcı
olarak zehirliyor; inf/nan sonraki HER `SUM(balance)` üzerinden yayılıyor,
yani uygulamadaki her Net Servet rakamı bozuluyordu.

Elle giriş yolu bu sınıfa karşı zaten korunuyordu
(utils/formatters.py::read_amount + input_filter); aynı disiplin CSV
yoluna hiç uygulanmamıştı.
"""
import os
import tempfile
import unittest

from services.migration_service import parse_transactions_csv

_HEADER = "tarih,tur,kategori,tutar,aciklama\n"


class CsvAmountValidationTest(unittest.TestCase):
    def _parse(self, amount_text):
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        self.addCleanup(os.unlink, path)
        with open(path, "w", encoding="utf-8") as f:
            f.write(_HEADER)
            f.write(f"2026-01-15,gider,Market,{amount_text},Test\n")
        return parse_transactions_csv(path)

    def test_infinity_is_rejected(self):
        records, skipped = self._parse("inf")
        self.assertEqual(records, [])
        self.assertEqual(skipped, 1)

    def test_negative_infinity_is_rejected(self):
        records, skipped = self._parse("-inf")
        self.assertEqual(records, [])
        self.assertEqual(skipped, 1)

    def test_nan_is_rejected(self):
        records, skipped = self._parse("nan")
        self.assertEqual(records, [])
        self.assertEqual(skipped, 1)

    def test_capitalised_infinity_spelling_is_rejected(self):
        """float() 'Infinity' ve 'NaN' yazımlarını da kabul eder."""
        for spelling in ("Infinity", "NaN", "INF"):
            with self.subTest(spelling=spelling):
                records, skipped = self._parse(spelling)
                self.assertEqual(records, [], f"{spelling} kabul edildi")
                self.assertEqual(skipped, 1)

    def test_ordinary_amount_still_imports(self):
        """Düzeltme geçerli tutarları engellememeli."""
        records, skipped = self._parse("1500.50")
        self.assertEqual(skipped, 0)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["amount"], 1500.50)

    def test_turkish_thousands_format_still_imports(self):
        # Değerin kendisi virgül içerdiği için CSV'de TIRNAKLI olmak
        # zorunda; tırnaksız yazılırsa virgül alan ayıracı olur (csv
        # modülünün kuralı, uygulamanın değil).
        records, skipped = self._parse('"1.234,56"')
        self.assertEqual(skipped, 0)
        self.assertEqual(records[0]["amount"], 1234.56)

    def test_zero_and_negative_are_still_rejected(self):
        for value in ("0", "-5"):
            with self.subTest(value=value):
                records, skipped = self._parse(value)
                self.assertEqual(records, [])
                self.assertEqual(skipped, 1)


if __name__ == "__main__":
    unittest.main()
