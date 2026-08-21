"""CSV dışa aktarımı elektronik tabloya formül teslim etmemeli.

ÖLÇÜLEN KUSUR: `export_all_to_csv` çözülmüş açıklama/kategori/varlık adını
`csv.writer` ile ham yazıyordu. Excel ve LibreOffice bir hücrenin İLK
karakterine bakıp formül olup olmadığına karar verir; `=`, `+`, `-`, `@` ile
(ve satır başı/sekme ile) başlayan bir hücre, dosya salt veri olsa bile
açılışta FORMÜL olarak değerlendirilir. Kullanıcı bir işlem açıklamasına
`=1+1` yazdıysa bu Archlence'ın hatası değil; ama o değeri elektronik tabloya
formül olarak teslim etmek Archlence'ın hatasıdır.

YUVARLAK YOLCULUK ŞARTI: kaçış tersinir olmalı. "Başına apostrof koydum"
demek yetmez — kullanıcının GERÇEKTEN apostrofla başlayan metni de
(`'+SUM(A1)`, `''=x`) dışa aktarım/içe aktarım turundan birebir dönmeli.
Bu yüzden apostrofla başlayan değerler de kaçırılır; içe aktarımda tam olarak
BİR apostrof soyulur ve eşleme tek anlamlı kalır.

SAYISAL KOLONLAR KAPSAM DIŞI: `tutar` ve `miktar` kolonları uygulamanın kendi
ürettiği sayılardır. Onlara apostrof eklemek elektronik tabloda sayı olmaktan
çıkarır ve kullanıcının dosyayla yapabileceği tek işi (toplam almak) bozardı.
"""
import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from services.migration_service import (
    CSV_HEADER,
    escape_csv_text,
    export_all_to_csv,
    parse_transactions_csv,
    unescape_csv_text,
)

# Excel/LibreOffice'in formül olarak yorumladığı başlangıçlar.
DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


class CsvEscapeContractTest(unittest.TestCase):
    """Saf kaçış/geri-çözme sözleşmesi — tersinir olmak ZORUNDA."""

    ROUND_TRIP_CASES = [
        "=1+1",
        "=cmd|'/c calc'!A1",
        "+SUM(A1:A9)",
        "-2+3",
        "@SUM(1)",
        "'+SUM(A1:A9)",
        "''=x",
        "'''",
        "\tsekmeyle baslar",
        "\rsatir basi",
        "\nyeni satir",
        "Market alışverişi",
        "Kira - Ocak",
        "2026-01-15",
        "1500.50",
        "",
        "'",
    ]

    def test_escape_then_unescape_returns_the_original(self):
        for value in self.ROUND_TRIP_CASES:
            with self.subTest(value=repr(value)):
                self.assertEqual(unescape_csv_text(escape_csv_text(value)), value)

    def test_escaped_value_never_starts_with_a_formula_trigger(self):
        for value in self.ROUND_TRIP_CASES:
            with self.subTest(value=repr(value)):
                escaped = escape_csv_text(value)
                if escaped:
                    self.assertFalse(
                        escaped.startswith(DANGEROUS),
                        f"{value!r} -> {escaped!r} hâlâ formül olarak açılır",
                    )

    def test_safe_text_is_left_byte_for_byte_alone(self):
        """Kaçış zararsız metinde KİMLİK olmalı; aksi hâlde her hücre bozulur."""
        for value in ("Market", "Kira Ocak", "2026-01-15", "1500.50", "Ünlü Şirket"):
            with self.subTest(value=value):
                self.assertEqual(escape_csv_text(value), value)


class CsvExportInjectionTest(unittest.TestCase):
    """GERÇEK üretim yolu: veritabanı -> export_all_to_csv -> dosya."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.db_path = root / "finance.db"
        self.export_path = root / "export.csv"
        self.key = os.urandom(32)

        self.db_patch = mock.patch("database.db.DB_NAME", str(self.db_path))
        self.key_patch = mock.patch(
            "utils.crypto._get_aead_key", return_value=self.key
        )
        self.db_patch.start()
        self.key_patch.start()
        self.addCleanup(self.tempdir.cleanup)
        self.addCleanup(self.db_patch.stop)
        self.addCleanup(self.key_patch.stop)

        from database.init_db import initialize_database
        from services.account_service import AccountService

        initialize_database()
        self.account_id = AccountService.create_account(
            "Dışa Aktarım Hesabı", "checking", initial_balance=100000
        )

    def _add(self, description, category="Market"):
        from services.transaction_service import TransactionService

        TransactionService.add_transaction(
            self.account_id, 125.50, "expense", category, description
        )

    def _rows(self):
        with open(self.export_path, "r", newline="", encoding="utf-8-sig") as handle:
            return list(csv.reader(handle))

    def test_dangerous_description_is_not_exported_as_a_formula(self):
        self._add("=1+1")
        export_all_to_csv(str(self.export_path))
        rows = self._rows()
        self.assertEqual(rows[0], CSV_HEADER)
        cells = [cell for row in rows[1:] for cell in row]
        self.assertNotIn("=1+1", cells)
        for cell in cells:
            self.assertFalse(
                cell.startswith(DANGEROUS),
                f"{cell!r} elektronik tabloda formül olarak açılır",
            )

    def test_dangerous_category_and_asset_name_are_neutralised(self):
        from services.asset_purchase_service import AssetPurchaseService

        self._add("normal", category="@cmd")
        AssetPurchaseService.create_purchase(
            asset_name='=HYPERLINK("http://x")',
            asset_code="+GCF",
            asset_type="Hisse",
            quantity=2,
            purchase_price=10,
            account_id=self.account_id,
        )
        export_all_to_csv(str(self.export_path))
        for row in self._rows()[1:]:
            for cell in row:
                self.assertFalse(
                    cell.startswith(DANGEROUS),
                    f"{cell!r} elektronik tabloda formül olarak açılır",
                )

    def test_numeric_columns_stay_numeric(self):
        """Tutar/miktar kolonları apostrofla bozulmamalı."""
        self._add("normal açıklama")
        export_all_to_csv(str(self.export_path))
        rows = self._rows()
        # SÜTUN İNDEKSİ BAŞLIKTAN OKUNUYOR, sabit değil: sürüm işareti
        # kolonu eklendiğinde sabit indeks sessizce yanlış sütunu okurdu.
        amount_index = CSV_HEADER.index("tutar")
        kind_index = CSV_HEADER.index("kayit_turu")
        islem = [r for r in rows[1:] if r[kind_index] == "islem"][0]
        self.assertEqual(float(islem[amount_index]), 125.50)

    def test_export_import_round_trip_restores_the_original_text(self):
        """Dışa aktar -> ayrıştır turu kullanıcının özgün metnini geri vermeli."""
        originals = ["=1+1", "'+SUM(A1:A9)", "''=x", "@cmd", "\tsekme", "Normal metin"]
        for text in originals:
            self._add(text)
        export_all_to_csv(str(self.export_path))
        records, skipped = parse_transactions_csv(str(self.export_path))
        self.assertEqual(skipped, 0)
        self.assertEqual(
            [r["description"] for r in records],
            [t.strip() for t in originals],
        )

    def test_third_party_csv_apostrophes_are_left_alone(self):
        """Bizim formatımız değilse kaçış geri çözülmez; yabancı dosya bozulmaz."""
        foreign = Path(self.tempdir.name) / "foreign.csv"
        foreign.write_text(
            "tarih,tur,kategori,tutar,aciklama\n"
            "2026-01-15,gider,Market,100.00,'alintili aciklama\n",
            encoding="utf-8",
        )
        records, skipped = parse_transactions_csv(str(foreign))
        self.assertEqual(skipped, 0)
        self.assertEqual(records[0]["description"], "'alintili aciklama")


if __name__ == "__main__":
    unittest.main()
